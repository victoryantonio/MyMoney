"""
Shared pytest fixtures/config.

Disables the slowapi rate limiter so the test suite (many login requests from
the same TestClient IP) is not throttled by the `10/minute` login limit.
"""

from app.core.rate_limit import limiter

limiter.enabled = False
