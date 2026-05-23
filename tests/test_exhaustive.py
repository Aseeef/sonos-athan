import pytest
import os
import socket
import signal
import time
from unittest.mock import MagicMock, patch
from sonos_athan import audio, sonos, scheduler, config
from sonos_athan.main import main as main_func

def test_audio_server_init(mocker):
    """Verify that AudioServerThread correctly initializes the HTTP server."""
    m_http = mocker.patch("sonos_athan.audio.ThreadingHTTPServer")
    thread = audio.AudioServerThread(8001, "/tmp")
    m_http.return_value.serve_forever.side_effect = lambda: None
    thread.run()
    assert m_http.called
    args, _ = m_http.call_args
    assert args[0] == ('', 8001)

def test_get_local_ip_fallback(mocker):
    """Verify IP detection logic under different network scenarios."""
    mock_socket = MagicMock()
    mock_socket.getsockname.return_value = ["192.168.1.50"]
    mocker.patch("socket.socket", return_value=mock_socket)
    ip = sonos.get_local_ip("192.168.1.1")
    assert ip == "192.168.1.50"
    mock_socket.connect.side_effect = Exception("No Route")
    ip = sonos.get_local_ip()
    assert ip == "127.0.0.1"

def test_discovery_strategy_fallback(mocker):
    """Test that it falls back to full multicast if cached IPs fail."""
    manager = sonos.SonosManager()
    manager.target_ips = ["1.1.1.1"]
    mocker.patch("soco.SoCo", side_effect=Exception("Offline"))
    m_discover = mocker.patch("soco.discover", return_value=[MagicMock(ip_address="192.168.1.100")])
    m_discover.return_value[0].player_name = "TV"
    success = manager.discover_and_group()
    assert success is True
    assert m_discover.called

def test_play_loop_state_transitions(mocker):
    """Test that the playback loop correctly waits through TRANSITIONING state."""
    manager = sonos.SonosManager()
    mock_master = MagicMock()
    manager.master = mock_master
    manager.target_speakers = [mock_master]
    
    # CRITICAL FIX: Mock discover_and_group so it doesn't exit early
    mocker.patch.object(manager, 'discover_and_group', return_value=True)
    
    mock_master.get_current_transport_info.side_effect = [
        {'current_transport_state': 'TRANSITIONING'},
        {'current_transport_state': 'PLAYING'},
        {'current_transport_state': 'STOPPED'}
    ]
    mocker.patch.object(manager, 'restore_state')
    mocker.patch("time.sleep")
    
    manager.is_playing_athan = True
    manager.play("test.mp3")
    assert mock_master.get_current_transport_info.call_count == 3

def test_download_all_audio_logic(mocker):
    """Verify that all required audio files are downloaded."""
    m_down = mocker.patch("sonos_athan.audio.download_audio")
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.makedirs")
    audio.download_all_audio()
    # Should call download twice (Athan and Fajr Athan)
    assert m_down.call_count == 2

def test_main_startup_sequence(mocker):
    """Verify that main() initializes all core components correctly."""
    m_down = mocker.patch("sonos_athan.main.download_all_audio")
    m_server = mocker.patch("sonos_athan.main.AudioServerThread")
    m_sched = mocker.patch("sonos_athan.main.AthanScheduler")
    m_signal = mocker.patch("signal.signal")
    
    # Mock scheduler.run to exit immediately
    m_sched.return_value.run.side_effect = StopIteration
    
    # Mock sys.exit to avoid exiting test process
    mocker.patch("sys.exit")
    
    try:
        # Call the aliased function
        main_func()
    except StopIteration:
        pass
        
    assert m_down.called
    assert m_server.called
    assert m_sched.called
    # Check that signals were registered
    assert m_signal.call_count >= 2

def test_tts_hashing_for_custom_text(mocker):
    """Verify that custom TTS messages use unique MD5 hashes for filenames."""
    mocker.patch("sonos_athan.audio.gTTS")
    mocker.patch("os.path.exists", return_value=True)
    
    text1 = "Message A"
    text2 = "Message B"
    
    file1 = audio.generate_reminder("Test", 0, custom_text=text1)
    file2 = audio.generate_reminder("Test", 0, custom_text=text2)
    
    assert file1 != file2
    assert file1.startswith("custom_")
    assert file2.startswith("custom_")

def test_audio_server_functional_serving(mocker):
    """Verify that AudioServerThread actually serves files from the directory."""
    import http.client
    import tempfile
    from sonos_athan.audio import AudioServerThread
    
    # Create a temporary file to serve
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Athan Content")
            
        # Use a random high port to avoid collisions
        port = 8999 
        server_thread = AudioServerThread(port, tmpdir)
        
        # Start server in a real background thread for a functional test
        # (We use a slightly more 'real' approach here since it's a simple HTTP server)
        import threading
        t = threading.Thread(target=server_thread.run, daemon=True)
        t.start()
        time.sleep(1) # Give it a moment to bind
        
        try:
            conn = http.client.HTTPConnection("localhost", port)
            conn.request("GET", "/test.txt")
            response = conn.getresponse()
            data = response.read().decode()
            
            assert response.status == 200
            assert data == "Athan Content"
        finally:
            server_thread.shutdown()

def test_adhan_sanity_and_ordering():
    """Verify that prayer times generated by the library are chronologically sane."""
    from sonos_athan.scheduler import AthanScheduler
    from adhanpy.calculation.CalculationMethod import CalculationMethod
    
    sched = AthanScheduler()
    # Mocking coordinates for NYC
    config.LATITUDE = 40.7128
    config.LONGITUDE = -74.0060
    
    # Test across multiple calculation methods to ensure adhanpy behaves as expected
    for method in [CalculationMethod.NORTH_AMERICA, CalculationMethod.UMM_AL_QURA]:
        config.CALCULATION_METHOD = method.name
        sched.update_times()
        
        times = sched.prayer_times
        # Assert logical ordering
        assert times["Fajr"] < times["Sunrise"]
        assert times["Sunrise"] < times["Dhuhr"]
        assert times["Dhuhr"] < times["Asr"]
        assert times["Asr"] < times["Maghrib"]
        assert times["Maghrib"] < times["Isha"]
        
        # Midnight should be after Maghrib but before the following noon
        assert times["Midnight"] > times["Maghrib"]
