#!/usr/bin/env python3
"""Seed data demo untuk Fase 4 (Flutter app).

Membuat user demo (`demo@mymoney.dev`) + transaksi 14 hari terakhir via
backend REST API, supaya line chart dashboard punya data untuk dicoba.

Idempotent: kalau user sudah ada, langsung pakai (tidak error).

Cara pakai:
    cd /root/project && PYTHONPATH=backend venv/bin/python scripts/seed_demo.py

Membaca kredensial dari .env — TIDAK pernah mencetak secret ke terminal.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    _load_env()
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    backend = os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")
    if not (url and anon and service):
        print("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY wajib ada di .env")
        return 1

    email = os.environ.get("DEMO_EMAIL", "demo@mymoney.dev")
    password = os.environ.get("DEMO_PASSWORD", "Demo1234!")

    admin_headers = {"apikey": service, "Authorization": f"Bearer {service}"}
    anon_headers = {"apikey": anon}

    # 1) Buat user demo (abaikan kalau sudah ada).
    created = False
    resp = httpx.post(
        f"{url}/auth/v1/admin/users",
        json={"email": email, "password": password, "email_confirm": True},
        headers=admin_headers,
    )
    if resp.status_code in (200, 201):
        created = True
        print(f"User demo dibuat: {email}")
    elif resp.status_code == 422 or "already been registered" in resp.text:
        print(f"User demo sudah ada (reuse): {email}")
    else:
        print(f"Gagal buat user: {resp.status_code} {resp.text[:200]}")
        return 1

    # 2) Login → access token.
    resp = httpx.post(
        f"{url}/auth/v1/token?grant_type=password",
        json={"email": email, "password": password},
        headers=anon_headers,
    )
    if resp.status_code != 200:
        print(f"Gagal login demo: {resp.status_code} {resp.text[:200]}")
        return 1
    token = resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # 3) Siapkan akun.
    resp = httpx.get(f"{backend}/api/accounts", headers=auth)
    resp.raise_for_status()
    accounts = resp.json()
    if accounts:
        account_id = accounts[0]["id"]
        print(f"Akun dipakai: {accounts[0]['account_name']}")
    else:
        resp = httpx.post(
            f"{backend}/api/accounts",
            json={"account_name": "Cash", "initial_balance": "500000.00"},
            headers=auth,
        )
        resp.raise_for_status()
        account_id = resp.json()["id"]
        print("Akun 'Cash' dibuat (saldo awal 500.000)")

    # 4) Kategori global yang tersedia (seeded migration 0001).
    resp = httpx.get(f"{backend}/api/categories", headers=auth)
    resp.raise_for_status()
    cats = {c["name"]: c for c in resp.json() if c.get("is_default")}
    needed = ["Food", "Transport", "Shopping", "Bills", "Salary", "Bonus"]
    missing = [n for n in needed if n not in cats]
    if missing:
        print(f"Kategori default tidak lengkap: {missing} — seed gagal?")
        return 1

    # 5) Seed transaksi 14 hari terakhir (idempotent per tanggal+merchant).
    today = date.today()
    seeded = 0
    for i in range(14):
        d = today - timedelta(days=i)
        day = d.day
        # Expense rutin harian (kecuali tanggal sudah punya data demo ini).
        rows = [
            ("expense", "Food", f"Makan siang {day}", _amt(day, 30000, 80000, 13)),
            ("expense", "Transport", f"Gojek {day}", _amt(day, 15000, 45000, 7)),
        ]
        if day % 3 == 0:
            rows.append(("expense", "Shopping", f"Belanja {day}", _amt(day, 50000, 250000, 29)))
        if day in (15, 20, 25):
            rows.append(("expense", "Bills", f"Tagihan {day}", _amt(day, 100000, 400000, 41)))
        if day == 25:
            rows.append(("income", "Salary", "Gaji bulanan", 5000000))
        if day == 20:
            rows.append(("income", "Bonus", "Bonus proyek", 2000000))
        for tx_type, cat, merchant, amount in rows:
            body = {
                "type": tx_type,
                "total_amount": f"{amount}.00",
                "category_id": cats[cat]["id"],
                "account_id": account_id,
                "merchant": merchant,
                "transaction_date": datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
            }
            resp = httpx.post(f"{backend}/api/transactions", json=body, headers=auth)
            if resp.status_code == 201:
                seeded += 1
            elif resp.status_code == 422 and "already" in resp.text.lower():
                pass  # duplikat dari run sebelumnya — abaikan
            else:
                print(f"  skip {merchant}: {resp.status_code} {resp.text[:120]}")

    print(f"\nSeeded {seeded} transaksi (14 hari, {today - timedelta(days=13)} s.d. {today})")
    if created:
        print(f"\n=== KREDENSIAL DEMO (untuk dicoba di app) ===")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")
        print("=" * 44)
    print("\nBackend:", backend)
    print("Supabase:", url)
    return 0


def _amt(day: int, lo: int, hi: int, seed: int) -> int:
    """Jumlah deterministik (pseudo-random stabil) untuk tiap hari."""
    n = (day * 37 + seed * 13) % (hi - lo) + lo
    return int(n)


if __name__ == "__main__":
    sys.exit(main())
