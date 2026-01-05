
import pytest
from unittest.mock import Mock, patch
import logging

# Ensure backend path is in sys.path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import fetch_channel_stats, fetch_shorts

class TestChannelStats:
    
    def test_fetch_channel_stats(self, monkeypatch):
        # Mock API Key
        monkeypatch.setattr("app.API_KEY", "test_key")
        
        # Mock requests.get
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "id": "UC123",
                    "statistics": {"subscriberCount": "1000"}
                },
                {
                    "id": "UC456",
                    "statistics": {"subscriberCount": "5000000"}
                }
            ]
        }
        
        with patch("requests.get", return_value=mock_resp) as mock_get:
            stats = fetch_channel_stats(["UC123", "UC456"])
            
            assert stats["UC123"] == 1000
            assert stats["UC456"] == 5000000
            
            # Verify API call
            args, kwargs = mock_get.call_args
            assert "https://www.googleapis.com/youtube/v3/channels" in args[0]
            assert kwargs["params"]["part"] == "statistics"
            assert "UC123,UC456" in kwargs["params"]["id"] or "UC456,UC123" in kwargs["params"]["id"]

    def test_fetch_shorts_integrates_subscriber_count(self, monkeypatch):
        monkeypatch.setattr("app.API_KEY", "test_key")
        
        # Mock helper functions
        def mock_parse_duration(d): return 30
        monkeypatch.setattr("app.parse_iso_duration", mock_parse_duration)
        
        # Mock channel stats
        def mock_fetch_channels(ids):
            return {"UC_TEST": 999}
        monkeypatch.setattr("app.fetch_channel_stats", mock_fetch_channels)

        # Mock Search Response
        mock_search_resp = Mock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {
            "items": [{"id": {"videoId": "vid1"}}]
        }
        
        # Mock Video Details Response
        mock_details_resp = Mock()
        mock_details_resp.status_code = 200
        mock_details_resp.json.return_value = {
            "items": [
                {
                    "id": "vid1",
                    "snippet": {
                        "title": "Test Video",
                        "channelId": "UC_TEST",
                        "channelTitle": "Test Channel"
                    },
                    "statistics": {"viewCount": "100"}
                }
            ]
        }

        with patch("requests.get", side_effect=[mock_search_resp, mock_details_resp]):
            results = fetch_shorts("test", 1, 7)
            
            assert len(results) == 1
            video = results[0]
            assert video["channel_id"] == "UC_TEST"
            assert video.get("subscriber_count") == 999

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
