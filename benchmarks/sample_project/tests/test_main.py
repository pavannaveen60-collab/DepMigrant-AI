"""Tests for sample project."""

import pytest
from sample_project.main import fetch_data, get_user_agent


def test_get_user_agent():
    """Test that user agent is returned."""
    ua = get_user_agent()
    assert isinstance(ua, str)
    assert len(ua) > 0


def test_fetch_data_mock(monkeypatch):
    """Test fetch_data with mocked requests."""
    import requests
    
    class MockResponse:
        def raise_for_status(self):
            pass
        
        def json(self):
            return {"test": "data"}
    
    def mock_get(*args, **kwargs):
        return MockResponse()
    
    monkeypatch.setattr(requests, "get", mock_get)
    
    result = fetch_data("https://example.com")
    assert result == {"test": "data"}