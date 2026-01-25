from datetime import timedelta
from src.services.ballot_service import BallotService

def test_format_time_delta():
    # Seconds
    assert BallotService.format_time_delta(timedelta(seconds=45)) == "45 seconds"
    
    # Minutes
    assert BallotService.format_time_delta(timedelta(minutes=5)) == "5 minutes"
    assert BallotService.format_time_delta(timedelta(seconds=119)) == "1 minutes"
    
    # Hours
    assert BallotService.format_time_delta(timedelta(hours=3)) == "3 hours"
    assert BallotService.format_time_delta(timedelta(minutes=119)) == "1 hours"
    
    # Days
    assert BallotService.format_time_delta(timedelta(days=2)) == "2 days"
    assert BallotService.format_time_delta(timedelta(hours=47)) == "1 days"
    assert BallotService.format_time_delta(timedelta(days=10)) == "10 days"
