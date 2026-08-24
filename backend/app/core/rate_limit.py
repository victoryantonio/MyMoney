"""
Rate limiting (slowapi) — CODING_RULES §2.10.

Single shared Limiter instance. Middleware is mounted in main.py; endpoints
that need limits use `@limiter.limit(...)`. Keyed by client IP.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
