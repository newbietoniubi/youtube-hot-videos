"""Unit tests for favorites functionality."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestFavoritesDB:
    """Tests for favorites database operations."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Set up a temporary database for each test."""
        import db
        # Override database path
        db.DB_PATH = tmp_path / "test_favorites.db"
        db.init_db()
        yield
        # Cleanup happens automatically with tmp_path

    def test_add_favorite(self):
        from db import add_favorite, get_favorites
        
        result = add_favorite(
            video_id="test123",
            title="Test Video",
            channel_id="ch1",
            channel_title="Test Channel"
        )
        
        assert result["success"] is True
        assert result["video_id"] == "test123"
        
        favorites = get_favorites()
        assert len(favorites) == 1
        assert favorites[0]["video_id"] == "test123"
        assert favorites[0]["title"] == "Test Video"

    def test_add_duplicate_favorite_reactivates(self):
        from db import add_favorite, remove_favorite, get_favorites
        
        add_favorite(video_id="v1", title="Video 1")
        remove_favorite("v1")
        
        # Should have no active favorites
        assert len(get_favorites()) == 0
        
        # Re-add should reactivate
        result = add_favorite(video_id="v1", title="Video 1")
        assert result.get("reactivated") is True
        assert len(get_favorites()) == 1

    def test_remove_favorite(self):
        from db import add_favorite, remove_favorite, get_favorites
        
        add_favorite(video_id="v1", title="Video 1")
        add_favorite(video_id="v2", title="Video 2")
        
        result = remove_favorite("v1")
        assert result["success"] is True
        
        favorites = get_favorites()
        assert len(favorites) == 1
        assert favorites[0]["video_id"] == "v2"

    def test_record_and_get_view_history(self):
        from db import add_favorite, record_view_count, get_view_history
        
        add_favorite(video_id="v1", title="Video 1")
        
        record_view_count("v1", view_count=1000, like_count=100, comment_count=10)
        record_view_count("v1", view_count=1500, like_count=150, comment_count=15)
        
        history = get_view_history("v1")
        assert len(history) == 2
        # Most recent first
        assert history[0]["view_count"] == 1500
        assert history[1]["view_count"] == 1000

    def test_get_active_favorites_for_tracking(self):
        from datetime import datetime, timedelta, timezone
        from db import add_favorite, get_active_favorites_for_tracking, get_connection
        
        add_favorite(video_id="v1", title="Recent Video")
        
        # Manually insert an old favorite (15 days ago)
        conn = get_connection()
        cursor = conn.cursor()
        old_date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        cursor.execute("""
            INSERT INTO favorites (video_id, title, created_at, is_active)
            VALUES (?, ?, ?, 1)
        """, ("v_old", "Old Video", old_date))
        conn.commit()
        conn.close()
        
        # Only recent one should be returned for tracking
        active = get_active_favorites_for_tracking()
        assert len(active) == 1
        assert active[0]["video_id"] == "v1"


class TestFavoritesAPI:
    """Tests for favorites API endpoints."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create test client with temporary database."""
        import db
        from app import app
        
        db.DB_PATH = tmp_path / "test_api.db"
        db.init_db()
        
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_get_favorites_empty(self, client):
        response = client.get('/favorites')
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 0
        assert data["favorites"] == []

    def test_add_favorite_via_api(self, client):
        response = client.post('/favorites', json={
            'video_id': 'test123',
            'title': 'Test Video',
            'channel_title': 'Test Channel',
            'view_count': 1000
        })
        assert response.status_code == 200
        assert response.get_json()["success"] is True
        
        # Verify it was added
        response = client.get('/favorites')
        assert response.get_json()["total"] == 1

    def test_add_favorite_without_video_id(self, client):
        response = client.post('/favorites', json={'title': 'Test'})
        assert response.status_code == 400

    def test_delete_favorite_via_api(self, client):
        # Add first
        client.post('/favorites', json={'video_id': 'v1', 'title': 'Test'})
        
        # Delete
        response = client.delete('/favorites/v1')
        assert response.status_code == 200
        assert response.get_json()["success"] is True
        
        # Verify deleted
        response = client.get('/favorites')
        assert response.get_json()["total"] == 0

    def test_get_history_not_found(self, client):
        response = client.get('/favorites/nonexistent/history')
        assert response.status_code == 404

    def test_refresh_favorites_updates_stats(self, client, monkeypatch):
        import app

        monkeypatch.setattr(app, "API_KEY", "test")
        client.post('/favorites', json={'video_id': 'v1', 'title': 'Test'})

        def mock_fetch_video_stats(video_ids):
            return {"v1": {"view_count": 123, "like_count": 5, "comment_count": 1}}

        monkeypatch.setattr(app, "fetch_video_stats", mock_fetch_video_stats)

        response = client.post('/favorites/refresh')
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["updated"] == 1

        history_resp = client.get('/favorites/v1/history')
        assert history_resp.status_code == 200
        history = history_resp.get_json()["history"]
        assert history[0]["view_count"] == 123


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
