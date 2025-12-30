import os
from src.config import get_proxy_url

def test_get_proxy_url_no_env():
    """Test that it returns None if ENV is empty"""
    if "LLM_PROXY" in os.environ:
        del os.environ["LLM_PROXY"]
    assert get_proxy_url() is None

def test_get_proxy_url_external():
    """Test that it returns external URL as is"""
    os.environ["LLM_PROXY"] = "http://example.com:3128"
    assert get_proxy_url() == "http://example.com:3128"

def test_get_proxy_url_localhost_replacement():
    """Test that localhost is replaced by host.docker.internal"""
    os.environ["LLM_PROXY"] = "http://127.0.0.1:12334"
    assert get_proxy_url() == "http://host.docker.internal:12334"
    
    os.environ["LLM_PROXY"] = "http://localhost:12334"
    assert get_proxy_url() == "http://host.docker.internal:12334"
