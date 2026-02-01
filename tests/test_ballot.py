from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from bs4 import BeautifulSoup
from httpx import AsyncClient
from itsdangerous import URLSafeTimedSerializer
from src.dependencies import get_ballot_service
from src.main import app
from src.models.ballot_models import Ballot, BallotCreate


async def test_dashboard_with_mocked_service(client: AsyncClient):
    # Setup mock service
    mock_service = AsyncMock()
    mock_ballot = Ballot(
        ballot_id="mock-123",
        owner_id="user-123",
        measure="Mocked Ballot",
        options=["Yes", "No"],
        allow_write_in=False,
        start_time=datetime.now(timezone.utc),
    )
    mock_service.list_ballots.return_value = [mock_ballot]

    # Simulate Login
    signer = URLSafeTimedSerializer("dev_secret_key_change_in_prod", salt="oponn-auth")
    token = signer.dumps("user-123")
    client.cookies.set("oponn_session", token)

    # Override dependency
    app.dependency_overrides[get_ballot_service] = lambda: mock_service

    try:
        response = await client.get("/")
        assert response.status_code == 200
        assert "Mocked Ballot" in response.text
        assert "my_ballots" in response.text
        mock_service.list_ballots.assert_called_once()
    finally:
        # Clean up override
        app.dependency_overrides.pop(get_ballot_service)


async def test_dashboard_and_create_navigation(client: AsyncClient):
    # Check dashboard
    response = await client.get("/")
    assert response.status_code == 200
    assert "oponn" in response.text
    assert "public_ballots" in response.text

    # Check create page
    response = await client.get("/create")
    assert response.status_code == 200
    assert "init_ballot" in response.text


async def test_full_ballot_lifecycle(client: AsyncClient):
    # 1. Create a ballot
    response = await client.post(
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
    ballot_id = response.headers["HX-Redirect"].split("/")[-1]

    # 3. Check vote page
    response = await client.get(f"/vote/{ballot_id}")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    option_alpha_id = None
    for label in soup.find_all("label", class_="radio-label"):
        if "Alpha" in label.get_text():
            input_el = label.find("input")
            if input_el:
                option_alpha_id = input_el["value"]
            break
    assert option_alpha_id is not None

    # 4. Cast a vote
    response = await client.post(
        f"/vote/{ballot_id}",
        data={"option_id": option_alpha_id},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/results/{ballot_id}"

    # 5. Check results
    response = await client.get(f"/results/{ballot_id}")
    assert response.status_code == 200
    assert "Refactor Test Ballot" in response.text
    assert "Alpha" in response.text


async def test_scheduled_ballot_validation(client: AsyncClient):
    # Test empty string for scheduled ballot (Required field check)
    response = await client.post(
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
    response = await client.post(
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


async def test_vote_button_states(client: AsyncClient):
    # 1. Create a future ballot via client
    future_st = datetime.now(timezone.utc) + timedelta(days=1)
    response = await client.post(
        "/create",
        data={
            "measure": "Future Ballot",
            "options_raw": "A, B",
            "start_time_type": "scheduled",
            "scheduled_start_time": future_st.isoformat(),
            "duration_mins": "60",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 204
    ballot_id = response.headers["HX-Redirect"].split("/")[-1]

    # 2. Check vote page for future ballot
    response = await client.get(f"/vote/{ballot_id}")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    button = soup.find("button", {"type": "submit"})
    assert button is not None
    assert button.has_attr("disabled")
    assert "starts in" in response.text.lower()

    # 3. Create an ended ballot via service (bypassing UI future-only validation)
    from src.database import get_sessionmaker

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        service = await get_ballot_service(session=session)
        past_st = datetime.now(timezone.utc) - timedelta(days=2)
        bc_ended = BallotCreate(
            measure="Ended Ballot",
            options=["A", "B"],
            allow_write_in=False,
            start_time=past_st,
            end_time=past_st + timedelta(hours=1),
        )
        ballot_ended = await service.create_ballot(bc_ended)
        # Note: create_ballot calls commit() internally in SQL repo

    # 4. Check vote page for ended ballot
    response = await client.get(f"/vote/{ballot_ended.ballot_id}")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    button = soup.find("button", {"type": "submit"})
    assert button is not None
    assert button.has_attr("disabled")
    assert "voting closed" in response.text.lower()


async def test_partial_rendering(client: AsyncClient):
    response = await client.get("/partials/start-time-input?start_time_type=scheduled")
    assert response.status_code == 200
    assert "commencement_timestamp" in response.text

    response = await client.get("/partials/start-time-input?start_time_type=now")
    assert response.status_code == 200
    assert response.text == ""
