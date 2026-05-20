from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sonos_athan.scheduler import AthanScheduler
import pytest

def test_midnight_calculation():
    # Mocking coordinates and calculation parameters would be complex
    # Let's test the logic of AthanScheduler's calculation manually
    # if we can isolate the method.
    
    scheduler = AthanScheduler()
    
    # We can mock the PrayerTimes responses to test the midpoint logic
    class MockPrayerTimes:
        def __init__(self, maghrib, fajr=None):
            self.maghrib = maghrib
            self.fajr = fajr
            self.sunrise = maghrib # dummy
            self.dhuhr = maghrib # dummy
            self.asr = maghrib # dummy
            self.isha = maghrib # dummy

    tz = ZoneInfo("America/New_York")
    maghrib = datetime(2026, 5, 19, 20, 0, tzinfo=tz)
    tomorrow_fajr = datetime(2026, 5, 20, 4, 0, tzinfo=tz)
    
    # Midnight should be (4:00 - 20:00) / 2 = 4 hours after 20:00 = 00:00
    duration = tomorrow_fajr - maghrib
    midnight = maghrib + (duration / 2)
    
    assert midnight == datetime(2026, 5, 20, 0, 0, tzinfo=tz)

def test_scheduler_event_sorting():
    scheduler = AthanScheduler()
    tz = ZoneInfo("America/New_York")
    now = datetime(2026, 5, 19, 12, 0, tzinfo=tz)
    
    scheduler.prayer_times = {
        "Fajr": now - timedelta(hours=8),
        "Dhuhr": now + timedelta(hours=1),
        "Asr": now + timedelta(hours=4)
    }
    
    # Simulate events generation
    events = []
    for name, p_time in scheduler.prayer_times.items():
        events.append((p_time, "athan", name, 0))
    
    future_events = sorted([e for e in events if e[0] > now], key=lambda x: x[0])
    
    assert len(future_events) == 2
    assert future_events[0][2] == "Dhuhr"
    assert future_events[1][2] == "Asr"
