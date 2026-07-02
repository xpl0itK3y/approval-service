from tests.helpers import auth_headers, create_payload

BASE = "/api/v1/workspaces/ws_1/approval-requests"
OTHER_BASE = "/api/v1/workspaces/ws_2/approval-requests"


def test_list_and_get(client):
    created = client.post(BASE, json=create_payload(), headers=auth_headers()).json()

    listing = client.get(BASE, headers=auth_headers())
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]

    single = client.get(f"{BASE}/{created['id']}", headers=auth_headers())
    assert single.status_code == 200
    assert single.json()["id"] == created["id"]


def test_get_missing_request_is_404(client):
    resp = client.get(f"{BASE}/does-not-exist", headers=auth_headers())
    assert resp.status_code == 404


def test_list_filters_by_status(client):
    created = client.post(BASE, json=create_payload(), headers=auth_headers()).json()
    client.post(BASE, json=create_payload(sourceId="pub_456"), headers=auth_headers())

    client.post(
        f"{BASE}/{created['id']}/approve", json={"comment": "ok"}, headers=auth_headers()
    )

    resp = client.get(BASE, params={"status": "approved"}, headers=auth_headers())
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_workspace_isolation_on_list(client):
    client.post(BASE, json=create_payload(), headers=auth_headers(workspace_id="ws_1"))
    client.post(
        OTHER_BASE, json=create_payload(), headers=auth_headers(workspace_id="ws_2")
    )

    ws1_listing = client.get(BASE, headers=auth_headers(workspace_id="ws_1"))
    ws2_listing = client.get(OTHER_BASE, headers=auth_headers(workspace_id="ws_2"))

    assert ws1_listing.json()["total"] == 1
    assert ws2_listing.json()["total"] == 1


def test_workspace_isolation_on_get(client):
    created = client.post(BASE, json=create_payload(), headers=auth_headers(workspace_id="ws_1")).json()

    # Same request id, but caller is authorized (and path scoped) to a different workspace.
    resp = client.get(f"{OTHER_BASE}/{created['id']}", headers=auth_headers(workspace_id="ws_2"))
    assert resp.status_code == 404


def test_cannot_use_token_from_one_workspace_to_read_another(client):
    client.post(BASE, json=create_payload(), headers=auth_headers(workspace_id="ws_1"))

    # Caller authorized for ws_1 tries to read ws_2's collection via path.
    resp = client.get(OTHER_BASE, headers=auth_headers(workspace_id="ws_1"))
    assert resp.status_code == 403


def test_read_requires_read_action(client):
    resp = client.get(BASE, headers=auth_headers(actions=("approval:create",)))
    assert resp.status_code == 403
