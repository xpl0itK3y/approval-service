from tests.helpers import auth_headers, create_payload

BASE = "/api/v1/workspaces/ws_1/approval-requests"


def _create(client):
    return client.post(BASE, json=create_payload(), headers=auth_headers()).json()


def test_approve(client):
    created = _create(client)
    resp = client.post(f"{BASE}/{created['id']}/approve", json={"comment": "Approved"}, headers=auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["decisionComment"] == "Approved"
    assert body["decidedByUserId"] == "usr_admin"


def test_reject(client):
    created = _create(client)
    resp = client.post(
        f"{BASE}/{created['id']}/reject", json={"reason": "Brand tone is wrong"}, headers=auth_headers()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["decisionReason"] == "Brand tone is wrong"


def test_cancel(client):
    created = _create(client)
    resp = client.post(
        f"{BASE}/{created['id']}/cancel", json={"reason": "Draft was removed"}, headers=auth_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_reject_requires_reason(client):
    created = _create(client)
    resp = client.post(f"{BASE}/{created['id']}/reject", json={}, headers=auth_headers())
    assert resp.status_code == 422


def test_cannot_transition_after_final_decision(client):
    created = _create(client)
    approve = client.post(
        f"{BASE}/{created['id']}/approve", json={"comment": "ok"}, headers=auth_headers()
    )
    assert approve.status_code == 200

    reject = client.post(
        f"{BASE}/{created['id']}/reject", json={"reason": "changed my mind"}, headers=auth_headers()
    )
    assert reject.status_code == 409

    cancel = client.post(
        f"{BASE}/{created['id']}/cancel", json={"reason": "changed my mind"}, headers=auth_headers()
    )
    assert cancel.status_code == 409


def test_decide_requires_decide_action(client):
    created = _create(client)
    resp = client.post(
        f"{BASE}/{created['id']}/approve",
        json={"comment": "ok"},
        headers=auth_headers(actions=("approval:read", "approval:create")),
    )
    assert resp.status_code == 403


def test_cancel_requires_cancel_action(client):
    created = _create(client)
    resp = client.post(
        f"{BASE}/{created['id']}/cancel",
        json={"reason": "no longer needed"},
        headers=auth_headers(actions=("approval:read", "approval:create")),
    )
    assert resp.status_code == 403


def test_decision_on_missing_request_is_404(client):
    resp = client.post(f"{BASE}/does-not-exist/approve", json={"comment": "ok"}, headers=auth_headers())
    assert resp.status_code == 404


def test_audit_log_records_actor_and_transitions(client):
    created = _create(client)
    client.post(f"{BASE}/{created['id']}/approve", json={"comment": "Approved"}, headers=auth_headers())

    resp = client.get(f"{BASE}/{created['id']}/audit-log", headers=auth_headers())
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 2
    assert entries[0]["action"] == "create"
    assert entries[0]["toStatus"] == "pending"
    assert entries[1]["action"] == "approve"
    assert entries[1]["fromStatus"] == "pending"
    assert entries[1]["toStatus"] == "approved"
    assert entries[1]["actorUserId"] == "usr_admin"
