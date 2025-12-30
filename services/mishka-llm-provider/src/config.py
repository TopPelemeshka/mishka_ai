import os

def get_proxy_url():
    """
    Get proxy URL from environment variables.
    If running in Docker and proxy points to localhost, replace it with host.docker.internal
    """
    proxy = os.getenv("LLM_PROXY")
    if not proxy:
        return None
    
    # Check if we are potentially inside a docker container (simple heuristic)
    # A more robust check could be looking for specific files like /.dockerenv
    # But for now we assume if LLM_PROXY is set and we're in this service, we might need replacement.
    
    if "localhost" in proxy or "127.0.0.1" in proxy:
        # Replace localhost/127.0.0.1 with host.docker.internal
        proxy = proxy.replace("localhost", "host.docker.internal")
        proxy = proxy.replace("127.0.0.1", "host.docker.internal")
        
    return proxy

LLM_PROXY = get_proxy_url()
