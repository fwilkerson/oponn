def test_reproduce_422_no_options(client):
    # Missing options_raw entirely
    response = client.post("/create", data={"measure": "Test Measure"})
    assert response.status_code == 200
    assert "field-error-msg" in response.text


def test_submit_empty_options_raw(client):
    # options_raw is provided but empty
    response = client.post(
        "/create", data={"measure": "Test Measure", "options_raw": ""}
    )
    assert response.status_code == 200
    assert "field-error-msg" in response.text


def test_reproduce_422_vote_no_option(client):
    # Create a ballot first
    response = client.post(
        "/create",
        data={"measure": "Vote Test", "options_raw": "A, B"},
        follow_redirects=False,
        headers={"HX-Request": "true"},
    )
    ballot_id = response.headers["HX-Redirect"].split("/")[-1]

    # Vote without selecting any option
    response = client.post(f"/vote/{ballot_id}", data={})
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 200
    # "error" is passed to vote_form context
    assert "err:" in response.text
