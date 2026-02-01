import random
import sys
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup  # type: ignore


def cast_single_vote(
    base_url: str, ballot_id: str, options: list[str], allow_write_in: bool
) -> bool:
    """Casts a single vote using a fresh session to bypass cookie-based vote limiting."""
    with httpx.Client(base_url=base_url, follow_redirects=True) as client:
        try:
            # 1. Get the vote page to fetch a fresh CSRF token
            response = client.get(f"/vote/{ballot_id}")
            response.raise_for_status()

            csrf_token = client.cookies.get("oponn_csrf_token")

            # 2. Prepare vote data
            data: dict[str, Any] = {}
            display_option: str = ""

            if allow_write_in and random.random() < 0.2:
                vote_option = "__write_in__"
                write_in_value = f"Sim-Write-in-{random.randint(1, 100)}"
                data = {"option_id": vote_option, "write_in_value": write_in_value}
                display_option = write_in_value
            else:
                if not options:
                    print("No options found for this ballot")
                    return False
                vote_option = random.choice(options)
                data = {"option_id": vote_option}
                display_option = vote_option

            # 3. Post the vote
            headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
            response = client.post(f"/vote/{ballot_id}", data=data, headers=headers)
            response.raise_for_status()

            print(f"Cast vote for '{display_option}'")
            return True

        except Exception as e:
            print(f"Error casting vote: {e}")
            return False


def simulate(ballot_id: str, num_votes: int = 10) -> None:
    base_url = "http://localhost:8000"

    # Initial fetch to get ballot metadata
    options: list[str] = []
    allow_write_in = False
    measure = ""

    with httpx.Client(base_url=base_url) as client:
        try:
            response = client.get(f"/vote/{ballot_id}")
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            h2 = soup.find("h2")
            if h2:
                measure = str(h2.text).replace("VOTE_ON: ", "")

            inputs = soup.find_all("input", {"type": "radio", "name": "option_id"})
            for inp in inputs:
                val = inp.get("value")
                if val and val != "__write_in__":
                    options.append(str(val))

            allow_write_in = soup.find("input", {"value": "__write_in__"}) is not None
        except Exception as e:
            print(f"Error fetching ballot metadata: {e}")
            return

    print(f"Simulating {num_votes} votes for ballot: {measure}")

    success_count = 0
    for i in range(num_votes):
        if cast_single_vote(base_url, ballot_id, options, allow_write_in):
            success_count += 1

        if i < num_votes - 1:
            time.sleep(0.2)

    print(f"Simulation complete: {success_count}/{num_votes} votes cast.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/simulate_votes.py <ballot_id> [num_votes]")
        sys.exit(1)

    try:
        bid = sys.argv[1]
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        simulate(bid, n)
    except ValueError:
        print("num_votes must be an integer.")
