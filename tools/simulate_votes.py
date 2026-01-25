import httpx
import random
import sys
import time
from bs4 import BeautifulSoup # type: ignore

def simulate(ballot_id, num_votes=10):
    base_url = "http://localhost:8000"
    
    with httpx.Client(base_url=base_url) as client:
        # Get ballot options by parsing the vote page
        try:
            response = client.get(f"/vote/{ballot_id}")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            measure = soup.find('h2').text.replace('VOTE_ON: ', '') # type: ignore
            
            # Extract options from radio inputs
            options = []
            inputs = soup.find_all('input', {'type': 'radio', 'name': 'option'})
            for inp in inputs:
                val = inp.get('value')
                if val and val != '__write_in__':
                    options.append(val)
            
            allow_write_in = soup.find('input', {'value': '__write_in__'}) is not None
            
        except Exception as e:
            print(f"Error fetching ballot {ballot_id} from UI: {e}")
            return

        print(f"Simulating {num_votes} votes for ballot: {measure}")
        
        for i in range(num_votes):
            if allow_write_in and random.random() < 0.2:
                vote_option = "__write_in__"
                write_in_value = f"Sim-Write-in-{random.randint(1, 100)}"
                data = {"option": vote_option, "write_in_value": write_in_value}
                display_option = write_in_value
            else:
                vote_option = random.choice(options)
                data = {"option": vote_option}
                display_option = vote_option
                
            try:
                # Use the UI endpoint (form submission)
                res = client.post(f"/vote/{ballot_id}", data=data)
                res.raise_for_status()
                print(f"Vote {i+1}/{num_votes}: Cast for '{display_option}'")
            except Exception as e:
                print(f"Error casting vote {i+1}: {e}")
            
            time.sleep(0.5)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/simulate_votes.py <ballot_id> [num_votes]")
        sys.exit(1)
        
    try:
        bid = int(sys.argv[1])
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        simulate(bid, n)
    except ValueError:
        print("Ballot ID and num_votes must be integers.")
