"""
Tests for the Casebook GUI FastAPI endpoints and security enforcement.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gui.server import app, SESSION_STATE
from src.ueba.db import get_connection


@pytest.fixture
def client():
    # Reset role to analyst by default
    SESSION_STATE["role"] = "analyst"
    with TestClient(app) as test_client:
        yield test_client


def test_get_session(client):
    res = client.get("/api/session")
    assert res.status_code == 200
    data = res.json()
    assert "role" in data
    assert "csrf_token" in data
    assert "permissions" in data


def test_update_role_valid(client):
    res = client.post("/api/session/role", json={"role": "senior_analyst"})
    assert res.status_code == 200
    assert res.json()["role"] == "senior_analyst"
    assert SESSION_STATE["role"] == "senior_analyst"


def test_update_role_invalid(client):
    res = client.post("/api/session/role", json={"role": "superadmin"})
    assert res.status_code == 422


def test_get_today(client):
    res = client.get("/api/today")
    assert res.status_code == 200
    data = res.json()
    assert "headline" in data
    assert "total_alerts" in data
    assert "top_cases" in data


def test_get_inbox(client):
    res = client.get("/api/inbox")
    assert res.status_code == 200
    data = res.json()
    assert "alerts" in data
    assert "count" in data
    assert isinstance(data["alerts"], list)


def test_get_case_detail(client):
    # Fetch first alert ID from inbox
    inbox_res = client.get("/api/inbox")
    alerts = inbox_res.json()["alerts"]
    if not alerts:
        pytest.skip("No alerts in DB")
    alert_id = alerts[0]["alert_id"]

    res = client.get(f"/api/case/{alert_id}")
    assert res.status_code == 200
    case = res.json()
    assert case["alert_id"] == alert_id
    assert "narrative" in case
    assert "indicators" in case
    assert "timeline_events" in case


def test_submit_feedback_analyst(client):
    inbox_res = client.get("/api/inbox")
    alerts = inbox_res.json()["alerts"]
    if not alerts:
        pytest.skip("No alerts in DB")
    alert_id = alerts[0]["alert_id"]

    SESSION_STATE["role"] = "analyst"
    res = client.post(
        f"/api/case/{alert_id}/feedback",
        json={
            "verdict": "benign_expected",
            "notes": "Verified business conference",
            "create_rule": True,
            "rule_days": 30,
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_submit_feedback_auditor_rejected(client):
    inbox_res = client.get("/api/inbox")
    alerts = inbox_res.json()["alerts"]
    if not alerts:
        pytest.skip("No alerts in DB")
    alert_id = alerts[0]["alert_id"]

    SESSION_STATE["role"] = "auditor"
    res = client.post(
        f"/api/case/{alert_id}/feedback",
        json={
            "verdict": "confirmed_suspicious",
            "notes": "Auditor attempting write",
        },
    )
    assert res.status_code == 403


def test_reidentification_requires_senior_analyst(client):
    SESSION_STATE["role"] = "analyst"
    res = client.post(
        "/api/case/reidentify",
        json={
            "pseudonym_id": "U-TEST01",
            "reason": "This is a valid long reason for investigation purpose.",
        },
    )
    assert res.status_code == 403
    assert "senior_analyst" in res.json()["detail"]


def test_reidentification_requires_20_chars(client):
    SESSION_STATE["role"] = "senior_analyst"
    res = client.post(
        "/api/case/reidentify",
        json={
            "pseudonym_id": "U-TEST01",
            "reason": "too short",
        },
    )
    assert res.status_code == 422 or res.status_code == 400


def test_reidentification_success(client):
    # Find a real pseudonym from users
    conn = get_connection()
    user = conn.execute("SELECT pseudonym FROM users LIMIT 1").fetchone()
    conn.close()
    if not user:
        pytest.skip("No users in DB")

    SESSION_STATE["role"] = "senior_analyst"
    res = client.post(
        "/api/case/reidentify",
        json={
            "pseudonym_id": user[0],
            "reason": "Official escalated insider investigation authorized by CISO.",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "real_user_id" in data
    assert data["real_user_id"].startswith("E")


def test_ledger_get_and_verify(client):
    res = client.get("/api/ledger")
    assert res.status_code == 200
    data = res.json()
    assert "entries" in data
    assert len(data["entries"]) > 0

    res_verify = client.post("/api/ledger/verify")
    assert res_verify.status_code == 200
    assert "valid" in res_verify.json()

    res_export = client.get("/api/ledger/export")
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers.get("content-type", "")


def test_safeguards_info(client):
    res = client.get("/api/safeguards")
    assert res.status_code == 200
    data = res.json()
    assert "live_safeguards" in data
    assert len(data["live_safeguards"]) >= 3


def test_rehearsal_scenarios(client):
    res = client.get("/api/rehearsal")
    assert res.status_code == 200
    data = res.json()
    assert "chapters" in data
    assert len(data["chapters"]) >= 8


def test_evidence_evaluation(client):
    res = client.get("/api/evidence")
    assert res.status_code == 200
    data = res.json()
    assert "evaluation" in data
    assert "ablation" in data
    assert data["evaluation"]["recall"] >= 0.85
