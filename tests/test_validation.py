from httpx import AsyncClient


async def test_measure_length_validation(client: AsyncClient):
    # Too long measure
    long_measure = "a" * 256
    response = await client.post(
        "/create",
        data={
            "measure": long_measure,
            "options_raw": "A\nB",
            "allow_write_in": False,
            "start_time_type": "now",
        },
        headers={"X-CSRF-Token": "test-token"},
    )
    assert response.status_code == 200
    assert "at most 255 characters" in response.text
    assert long_measure in response.text  # Sticky value
    assert "A\nB" in response.text  # Sticky options

    # Empty measure
    response = await client.post(
        "/create",
        data={
            "measure": "",
            "options_raw": "A\nB",
            "allow_write_in": False,
            "start_time_type": "now",
        },
        headers={"X-CSRF-Token": "test-token"},
    )
    assert response.status_code == 200
    assert "at least 3 characters" in response.text


async def test_options_count_validation(client: AsyncClient):
    # Too few options
    response = await client.post(
        "/create",
        data={
            "measure": "Test Ballot",
            "options_raw": "OneOption",
            "allow_write_in": False,
            "start_time_type": "now",
        },
        headers={"X-CSRF-Token": "test-token"},
    )
    assert response.status_code == 200
    assert "at least 2 options" in response.text
    assert "OneOption" in response.text


async def test_option_length_validation(client: AsyncClient):
    # Too long option
    long_option = "a" * 65
    # Provide 3 options so that even if one is invalid, we don't hit the "at least 2 options" error
    # which seems to take precedence in the UI rendering.
    response = await client.post(
        "/create",
        data={
            "measure": "Test Ballot",
            "options_raw": f"Valid1, Valid2, {long_option}",
            "allow_write_in": False,
            "start_time_type": "now",
        },
        headers={"X-CSRF-Token": "test-token"},
    )
    assert response.status_code == 200
    assert "between 1 and 64 characters" in response.text
    assert long_option in response.text


async def test_vote_write_in_length_validation(client: AsyncClient):
    # 1. Create a ballot
    create_resp = await client.post(
        "/create",
        data={
            "measure": "Write-in Test",
            "options_raw": "A\nB",
            "allow_write_in": True,
            "start_time_type": "now",
        },
        headers={"X-CSRF-Token": "test-token"},
    )
    ballot_id = create_resp.headers["location"].split("/")[-1]

    # 2. Submit too long write-in
    long_write_in = "w" * 65
    vote_resp = await client.post(
        f"/vote/{ballot_id}",
        data={"option_id": "__write_in__", "write_in_value": long_write_in},
        headers={"X-CSRF-Token": "test-token"},
    )

    assert vote_resp.status_code == 200
    assert "at most 64 characters" in vote_resp.text
    # Write-in is not sticky in template, so we don't assert it's present


async def test_scheduled_start_time_persistence(client: AsyncClient):
    """Test that scheduled start times are correctly passed and rendered on error."""
    # 1. Submit with invalid options but valid start time
    # Note: We must provide a timezone-aware ISO string to avoid 500 errors
    response = await client.post(
        "/create",
        data={
            "measure": "Future Ballot",
            "options_raw": "One",
            "allow_write_in": False,
            "start_time_type": "scheduled",
            "scheduled_start_time": "2025-01-01T12:00:00+00:00",
        },
        headers={"X-CSRF-Token": "test-token"},
    )

    assert response.status_code == 200
    assert "at least 2 options" in response.text
    # Verify Sticky Values (Select option uses 'selected', not checked)
    # Check loosely for presence of value and selected attribute
    assert 'value="scheduled"' in response.text
    assert "selected" in response.text
    assert 'value="2025-01-01T12:00:00+00:00"' in response.text
    # Verify the partial for date input is rendered
    assert 'id="scheduled-start-container"' in response.text
