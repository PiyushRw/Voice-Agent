from fastapi import Header

def authorized(x_demo_key: str = Header(default="")):
    """Demo mode: no workspace access key required."""
    return None
