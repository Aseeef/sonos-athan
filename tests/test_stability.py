import pytest
import time
from sonos_athan.scheduler import AthanScheduler
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock

def test_scheduler_loop_chunks(mocker):
    """Test that the scheduler uses short intervals for the main loop."""
    scheduler = AthanScheduler()
    tz = ZoneInfo("America/New_York")
    
    # Mock update_times to succeed
    mocker.patch.object(scheduler, 'update_times', return_value=True)
    
    # Event is 100 seconds away
    now = datetime.now(tz)
    scheduler.prayer_times = {"Test": now + timedelta(seconds=100)}
    
    # Mock wait to return True (exit) on the second call
    # 1st call should be 30s chunk
    # 2nd call should be exit signal
    mock_wait = mocker.patch.object(scheduler.stop_event, 'wait', side_effect=[False, True])
    
    # Run the loop logic once manually or trigger run() and break
    try:
        scheduler.run()
    except:
        pass
        
    # First wait should be exactly 30s
    mock_wait.assert_any_call(30)

def test_scheduler_calculation_retry_logic(mocker):
    """Test that update_times catches exceptions and returns False."""
    scheduler = AthanScheduler()
    scheduler.current_day = None # Force calculation
    
    # Simulate a network failure in PrayerTimes (first external call in update_times)
    mocker.patch("sonos_athan.scheduler.PrayerTimes", side_effect=Exception("Internet Down"))
    
    success = scheduler.update_times()
    assert success is False

def test_sonos_guaranteed_restoration(mocker):
    """Test that restore_state is called even if play_uri fails."""
    from sonos_athan.sonos import SonosManager
    manager = SonosManager()
    
    # Mock master to fail
    mock_master = MagicMock()
    mock_master.play_uri.side_effect = Exception("Sonos Disconnected")
    manager.master = mock_master
    
    # Setup state to restore
    manager.original_states = {"1.1.1.1": {'volume': 10, 'original_coordinator_ip': '1.1.1.1', 'is_coordinator': True}}
    manager.target_speakers = [mock_master]
    mock_master.ip_address = "1.1.1.1"
    
    # Mock restore_state to verify it's called
    mock_restore = mocker.patch.object(manager, 'restore_state')
    
    # Play should fail but restore should be called
    manager.play("test.mp3")
    
    assert mock_restore.called
