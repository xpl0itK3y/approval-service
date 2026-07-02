from tests.helpers import auth_headers, create_payload

BASE = "/api/v1/workspaces/ws_1/approval-requests"


def test_repeated_create_with_same_key_returns_same_request(client):
    headers = {**auth_headers(), "Idempotency-Key": "key-1"}
    first = client.post(BASE, json=create_payload(), headers=headers)
    second = client.post(BASE, json=create_payload(), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    listing = client.get(BASE, headers=auth_headers())
    assert listing.json()["total"] == 1


def test_same_key_different_payload_conflicts(client):
    headers = {**auth_headers(), "Idempotency-Key": "key-2"}
    first = client.post(BASE, json=create_payload(), headers=headers)
    second = client.post(BASE, json=create_payload(title="different title"), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409


def test_create_without_key_creates_duplicates(client):
    resp1 = client.post(BASE, json=create_payload(), headers=auth_headers())
    resp2 = client.post(BASE, json=create_payload(), headers=auth_headers())

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["id"] != resp2.json()["id"]


def test_repeated_decision_with_same_key_replays_result(client):
    create_resp = client.post(BASE, json=create_payload(), headers=auth_headers())
    request_id = create_resp.json()["id"]

    headers = {**auth_headers(), "Idempotency-Key": "approve-key-1"}
    first = client.post(f"{BASE}/{request_id}/approve", json={"comment": "Approved"}, headers=headers)
    second = client.post(f"{BASE}/{request_id}/approve", json={"comment": "Approved"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
