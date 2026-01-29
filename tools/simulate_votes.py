import random
import sys
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup  # type: ignore


def simulate(ballot_id: str, num_votes: int = 10) -> None:
    base_url = "http://localhost:8000"

    with httpx.Client(base_url=base_url, follow_redirects=True) as client:
        # Get ballot options by parsing the vote page
        try:
            response = client.get(f"/vote/{ballot_id}")
            _ = response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            h2 = soup.find("h2")
            if h2 is None:
                raise ValueError("Could not find ballot measure title")
            measure = str(h2.text).replace("VOTE_ON: ", "")

            # Extract options from radio inputs
            options: list[str] = []
            inputs = soup.find_all("input", {"type": "radio", "name": "option"})
            for inp in inputs:
                val = inp.get("value")
                if val and val != "__write_in__":
                    options.append(str(val))

            allow_write_in = soup.find("input", {"value": "__write_in__"}) is not None

            # Get CSRF token from cookie
            csrf_token = client.cookies.get("oponn_csrf_token")
            if not csrf_token:
                print("Warning: No CSRF token found in cookies. Simulation might fail.")

        except Exception as e:
            print(f"Error fetching ballot {ballot_id} from UI: {e}")
            return

        print(f"Simulating {num_votes} votes for ballot: {measure}")

        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

        for i in range(num_votes):
            data: dict[str, Any] = {}
            display_option: str = ""
            if allow_write_in and random.random() < 0.2:
                vote_option = "__write_in__"
                write_in_value = f"Sim-Write-in-{random.randint(1, 100)}"
                data = {"option": vote_option, "write_in_value": write_in_value}
                display_option = write_in_value
            else:
                if not options:
                    print("No options found for this ballot")
                    return
                vote_option = random.choice(options)
                data = {"option": vote_option}
                display_option = vote_option

            try:
                # Use the UI endpoint (form submission)
                _ = client.post(f"/vote/{ballot_id}", data=data, headers=headers)
                client.cookies.set(f"voted_{ballot_id}", "")  # Clear voted cookie
                print(f"Vote {i + 1}/{num_votes}: Cast for '{display_option}'")
            except Exception as e:
                print(f"Error casting vote {i + 1}: {e}")

            time.sleep(0.5)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/simulate_votes.py <ballot_id> [num_votes]")
        sys.exit(1)

    try:
        bid = sys.argv[1]
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        simulate(bid, n)
    except ValueError:
        print("Ballot ID and num_votes must be integers.")
