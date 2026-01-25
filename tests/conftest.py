import pytest
import threading
import time
import uvicorn
import socket
import os
from fastapi.testclient import TestClient
from src.main import app
from src.dependencies import validate_csrf, _ballot_service
from src.repositories.ballot_repository import InMemoryBallotRepository


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(autouse=True)
def reset_service():
    """Resets the global service state before each test to ensure isolation."""
    # Always clear SSE and locks
    _ballot_service._sse_queues.clear()
    _ballot_service._locks.clear()

    # Reset in-memory repo if that's what we are using
    _ballot_repo = _ballot_service.repository
    if isinstance(_ballot_repo, InMemoryBallotRepository):
        _ballot_repo.ballots_db.clear()
        _ballot_repo.votes_db.clear()
        _ballot_repo.ballot_id_counter = 0


@pytest.fixture
def client():
    # Override CSRF for local TestClient tests
    app.dependency_overrides[validate_csrf] = lambda: None

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def server_url():
    """Starts a real server in a background thread for SSE and functional tests."""
    # Disable CSRF for the background server during tests
    os.environ["OPONN_SKIP_CSRF"] = "true"

    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    # Wait for server to start
    url = f"http://127.0.0.1:{port}"
    start_time = time.time()
    while time.time() - start_time < 5:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)
    else:
        pytest.fail("Server failed to start in background")

    yield url

    server.should_exit = True
    thread.join(timeout=2)
    os.environ.pop("OPONN_SKIP_CSRF", None)
