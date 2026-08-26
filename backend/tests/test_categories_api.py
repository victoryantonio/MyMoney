"""
API tests for category management (needed by Phase 4 Android app):
  - GET/POST list & create
  - PUT edit (rename / re-type) — new endpoint
  - DELETE soft-delete
Runs against the full FastAPI app via TestClient (same pattern as
report tests). Requires a running PostgreSQL.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per call → Bearer headers (skips in CI without creds)."""
    return supabase_factory


def _create(headers: dict[str, str], name: str, type_: str = "expense"):
    return client.post("/api/categories", json={"name": name, "type": type_}, headers=headers)


def _first_global_id(headers: dict[str, str]) -> str:
    resp = client.get("/api/categories", headers=headers)
    assert resp.status_code == 200
    for cat in resp.json():
        if cat["is_default"]:
            return cat["id"]
    raise AssertionError("no global default category seeded")


# ── Create / list ────────────────────────────────────────────────────────────


def test_create_category(auth):
    headers = auth("cat_create")
    resp = _create(headers, "Hobi", "expense")
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Hobi"
    assert data["type"] == "expense"
    assert data["is_default"] is False
    assert data["user_id"] is not None


def test_create_duplicate_conflict(auth):
    headers = auth("cat_dup")
    assert _create(headers, "Kuliner").status_code == 201
    resp = _create(headers, "Kuliner")  # same owner, same name+type
    assert resp.status_code == 409


def test_create_shadowing_global_conflict(auth):
    """A custom category must not shadow a global default of the same name."""
    headers = auth("cat_shadow")
    resp = _create(headers, "Food", "expense")  # global 'Food/expense' exists
    assert resp.status_code == 409


def test_list_includes_custom_and_global(auth):
    headers = auth("cat_list")
    assert _create(headers, "Olahraga", "expense").status_code == 201
    resp = client.get("/api/categories", headers=headers)
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()}
    assert "Olahraga" in names
    assert any(c["is_default"] for c in resp.json())


# ── PUT edit ─────────────────────────────────────────────────────────────────


def test_put_rename(auth):
    headers = auth("cat_rename")
    created = _create(headers, "OldName").json()
    resp = client.put(
        f"/api/categories/{created['id']}",
        json={"name": "NewName"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "NewName"
    assert data["type"] == "expense"
    assert data["id"] == created["id"]


def test_put_change_type(auth):
    headers = auth("cat_type")
    created = _create(headers, "Freelance", "expense").json()
    resp = client.put(
        f"/api/categories/{created['id']}",
        json={"type": "income"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["type"] == "income"


def test_put_global_category_forbidden(auth):
    headers = auth("cat_global")
    global_id = _first_global_id(headers)
    resp = client.put(
        f"/api/categories/{global_id}",
        json={"name": "Hacked"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_put_other_users_category_not_found(auth):
    headers_a = auth("cat_owner_a")
    headers_b = auth("cat_owner_b")
    created = _create(headers_a, "Privat").json()
    resp = client.put(
        f"/api/categories/{created['id']}",
        json={"name": "Diubah"},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_put_duplicate_conflict(auth):
    headers = auth("cat_putdup")
    _create(headers, "Taken", "expense")
    other = _create(headers, "Free", "expense").json()
    resp = client.put(
        f"/api/categories/{other['id']}",
        json={"name": "Taken"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_put_invalid_type_422(auth):
    headers = auth("cat_badtype")
    created = _create(headers, "Valid").json()
    resp = client.put(
        f"/api/categories/{created['id']}",
        json={"type": "hack"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── DELETE ───────────────────────────────────────────────────────────────────


def test_delete_category(auth):
    headers = auth("cat_delete")
    created = _create(headers, "Buang").json()
    resp = client.delete(f"/api/categories/{created['id']}", headers=headers)
    assert resp.status_code == 204
    listed = client.get("/api/categories", headers=headers).json()
    assert all(c["id"] != created["id"] for c in listed)


def test_delete_global_category_forbidden(auth):
    headers = auth("cat_delglobal")
    global_id = _first_global_id(headers)
    resp = client.delete(f"/api/categories/{global_id}", headers=headers)
    assert resp.status_code == 403


def test_delete_requires_auth():
    resp = client.delete(f"/api/categories/{uuid.uuid4()}")
    assert resp.status_code == 401
