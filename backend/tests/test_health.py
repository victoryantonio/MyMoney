"""
Integration test for the /health endpoint.

Auth v2 (Fase 1) moved registration/login to Supabase Auth — there are no
/api/auth/* routes in the app anymore, so only the health check remains here.
API auth behavior is covered by the live-Supabase E2E checks (walkthrough)
and by the `supabase_factory`-gated tests (skipped in CI without credentials).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
