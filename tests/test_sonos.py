import pytest
from unittest.mock import MagicMock, patch
from sonos_athan.sonos import SonosManager

@pytest.fixture
def manager():
    return SonosManager()

def test_state_restoration_with_failures(manager, mocker):
    """Test that restoration continues even if one speaker fails to respond."""
    # Create two mock speakers
    s1 = MagicMock(name="Speaker1")
    s1.ip_address = "192.168.1.10"
    s1.player_name = "Living Room"
    
    s2 = MagicMock(name="Speaker2")
    s2.ip_address = "192.168.1.11"
    s2.player_name = "Kitchen"
    
    manager.target_speakers = [s1, s2]
    
    # Define a state where s1 fails during volume restoration
    manager.original_states = {
        "192.168.1.10": {
            'volume': 20, 
            'original_coordinator_ip': "192.168.1.10", 
            'is_coordinator': True,
            'track_info': {'uri': 'x-rincon:abc'},
            'transport_info': {'current_transport_state': 'PLAYING'}
        },
        "192.168.1.11": {
            'volume': 15, 
            'original_coordinator_ip': "192.168.1.11", 
            'is_coordinator': True,
            'track_info': None,
            'transport_info': None
        }
    }
    
    # Mock property setting failure for s1
    type(s1).volume = mocker.PropertyMock(side_effect=Exception("Connection Timeout"))
    
    # We should NOT crash
    manager.restore_state()
    
    # Verify s2 was still processed
    s2.volume = 15 # Check that the setter was called
    assert s2.unjoin.called

def test_complex_group_restoration(manager, mocker):
    """Test restoring a setup where speakers were originally in different groups."""
    # s1/s2 were grouped together, s3 was standalone
    s1 = MagicMock(name="Coord1")
    s1.ip_address = "1.1.1.1"
    s2 = MagicMock(name="Follower1")
    s2.ip_address = "1.1.1.2"
    s3 = MagicMock(name="Coord2")
    s3.ip_address = "1.1.1.3"
    
    manager.target_speakers = [s1, s2, s3]
    manager.original_states = {
        "1.1.1.1": {'volume': 10, 'is_coordinator': True, 'original_coordinator_ip': "1.1.1.1", 'track_info': {'uri': 'uri1'}, 'transport_info': {'current_transport_state': 'PLAYING'}},
        "1.1.1.2": {'volume': 10, 'is_coordinator': False, 'original_coordinator_ip': "1.1.1.1", 'track_info': None, 'transport_info': None},
        "1.1.1.3": {'volume': 20, 'is_coordinator': True, 'original_coordinator_ip': "1.1.1.3", 'track_info': {'uri': 'uri2'}, 'transport_info': {'current_transport_state': 'STOPPED'}}
    }
    
    # Mock SoCo class to return our mocks based on IP
    m_soco = mocker.patch("soco.SoCo", side_effect=lambda ip: s1 if ip == "1.1.1.1" else (s2 if ip == "1.1.1.2" else s3))
    
    manager.restore_state()
    
    # s1 should have resumed its music
    s1.play_uri.assert_called_with('uri1', title=mocker.ANY)
    s1.play.assert_called_once()
    
    # s2 should have re-joined s1
    s2.join.assert_called_with(s1)
    
    # s3 should have resumed its uri2 but stayed stopped
    s3.play_uri.assert_called_with('uri2', title=mocker.ANY)
    assert not s3.play.called
    assert s3.stop.called
