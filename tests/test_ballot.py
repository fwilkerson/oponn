from datetime import datetime, timedelta, timezone
import pytest
from src.main import app
from src.models.ballot_models import BallotCreate


from unittest.mock import MagicMock
from src.dependencies import get_ballot_service
from src.models.ballot_models import Ballot


@pytest.mark.asyncio
async def test_dashboard_with_mocked_service(client):
    # Setup mock service
    mock_service = MagicMock()
    mock_ballot = Ballot(
        ballot_id=999,
        measure="Mocked Ballot",
        options=["Yes", "No"],
        allow_write_in=False,
        start_time=datetime.now(timezone.utc),
    )
    mock_service.list_ballots.return_value = [mock_ballot]

    # Override dependency
    app.dependency_overrides[get_ballot_service] = lambda: mock_service

    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "Mocked Ballot" in response.text
        mock_service.list_ballots.assert_called_once()
    finally:
        # Clean up override
        app.dependency_overrides.pop(get_ballot_service)


@pytest.mark.asyncio
async def test_dashboard_and_create_navigation(client):
    # Check dashboard
    response = client.get("/")
    assert response.status_code == 200
    assert "oponn" in response.text
    assert "active_ballots" in response.text

    # Check create page
    response = client.get("/create")
    assert response.status_code == 200
    assert "new_ballot" in response.text


@pytest.mark.asyncio
async def test_full_ballot_lifecycle(client):
    # 1. Create a ballot
    response = client.post(
        "/create",
        data={
            "measure": "Refactor Test Ballot",
            "options_raw": "Alpha, Beta",
            "allow_write_in": "on",
            "duration_mins": "60",
        },
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 204
    ballot_id = int(response.headers["HX-Redirect"].split("/")[-1])

    # 3. Check vote page
    response = client.get(f"/vote/{ballot_id}")
    assert response.status_code == 200

    # 4. Cast a vote
    response = client.post(
        f"/vote/{ballot_id}",
        data={"option": "Alpha"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/results/{ballot_id}"

    # 5. Check results
    response = client.get(f"/results/{ballot_id}")
    assert response.status_code == 200
    assert "Refactor Test Ballot" in response.text
    assert "Alpha" in response.text


@pytest.mark.asyncio
async def test_scheduled_ballot_validation(client):
    # Test empty string for scheduled ballot (Required field check)
    response = client.post(
        "/create",
        data={
            "measure": "Bug Reproduction Ballot",
            "options_raw": "Yes, No",
            "start_time_type": "scheduled",
            "scheduled_start_time": "",
            "duration_mins": "60",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "Scheduled start time is required" in response.text

    # Test past date
    past_date = datetime.now(timezone.utc) - timedelta(hours=1)
    response = client.post(
        "/create",
        data={
            "measure": "Past Ballot",
            "options_raw": "Yes, No",
            "start_time_type": "scheduled",
            "scheduled_start_time": past_date.isoformat(),
            "duration_mins": "60",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "Scheduled start time must be in the future" in response.text


@pytest.mark.asyncio
async def test_vote_button_states(client):
    # Create a future ballot via service
    future_st = datetime.now(timezone.utc) + timedelta(days=1)
    bc = BallotCreate(
        measure="Future Ballot",
        options=["A", "B"],
        allow_write_in=False,
        start_time=future_st,
    )
    ballot = app.state.ballot_service.create_ballot(bc)

    response = client.get(f"/vote/{ballot.ballot_id}")
    assert 'button type="submit" disabled' in response.text
    assert "starts in" in response.text

    # Create an ended ballot
    past_st = datetime.now(timezone.utc) - timedelta(hours=2)
    past_et = datetime.now(timezone.utc) - timedelta(hours=1)
    bc_ended = BallotCreate(
        measure="Ended Ballot",
        options=["B", "C"],
        allow_write_in=False,
        start_time=past_st,
        end_time=past_et,
    )
    ballot_ended = app.state.ballot_service.create_ballot(bc_ended)

    response = client.get(f"/vote/{ballot_ended.ballot_id}")
    assert 'button type="submit" disabled' in response.text
    assert "voting closed" in response.text


@pytest.mark.asyncio
async def test_partial_rendering(client):
    response = client.get("/partials/start-time-input?start_time_type=scheduled")
    assert response.status_code == 200
    assert "commencement_timestamp" in response.text

    response = client.get("/partials/start-time-input?start_time_type=now")
    assert response.status_code == 200
    assert response.text == ""
