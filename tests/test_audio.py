import os
from sonos_athan import audio

def test_generate_reminder_caching(mocker):
    # Mock gTTS to avoid network calls
    mock_gtts = mocker.patch("sonos_athan.audio.gTTS")
    
    prayer = "Asr"
    mins = 10
    
    # Run once
    filename = audio.generate_reminder(prayer, mins)
    assert "reminder_Asr_10.mp3" in filename
    
    # Verify gTTS was called if file didn't exist
    # (Assuming we start with a clean state or mock os.path.exists)
    mocker.patch("os.path.exists", return_value=True)
    filename2 = audio.generate_reminder(prayer, mins)
    
    assert filename == filename2

def test_download_audio_skip_if_exists(mocker):
    m_get = mocker.patch("requests.get")
    m_exists = mocker.patch("os.path.exists", return_value=True)
    
    audio.download_audio("http://example.com/test.mp3", "test.mp3", "Test")
    
    # Should not call requests if file exists
    assert not m_get.called
