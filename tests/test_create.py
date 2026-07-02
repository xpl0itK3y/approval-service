from tests.helpers import auth_headers, create_payload

BASE = "/api/v1/workspaces/ws_1/approval-requests"


def test_create_success(client):
    resp = client.post(BASE, json=create_payload(), headers=auth_headers())
    assert resp.status_code == 201
    body = resp.json()
    assert body["sourceType"] == "publication"
    assert body["sourceId"] == "pub_123"
    assert body["status"] == "pending"
    assert body["reviewerUserIds"] == ["usr_1", "usr_2"]
    assert body["workspaceId"] == "ws_1"
    assert body["createdByUserId"] == "usr_admin"
    assert body["id"]


def test_create_rejects_unknown_source_type(client):
    resp = client.post(BASE, json=create_payload(sourceType="bogus"), headers=auth_headers())
    assert resp.status_code == 422


def test_create_rejects_empty_reviewer_list(client):
    resp = client.post(BASE, json=create_payload(reviewerUserIds=[]), headers=auth_headers())
    assert resp.status_code == 422


def test_create_rejects_unknown_fields(client):
    resp = client.post(BASE, json=create_payload(secretToken="abc"), headers=auth_headers())
    assert resp.status_code == 422


def test_create_requires_auth_headers(client):
    resp = client.post(BASE, json=create_payload())
    assert resp.status_code == 401


def test_create_requires_create_action(client):
    headers = auth_headers(actions=("approval:read",))
    resp = client.post(BASE, json=create_payload(), headers=headers)
    assert resp.status_code == 403


def test_create_rejects_workspace_mismatch(client):
    headers = auth_headers(workspace_id="ws_other")
    resp = client.post(BASE, json=create_payload(), headers=headers)
    assert resp.status_code == 403
