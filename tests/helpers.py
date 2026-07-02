ALL_ACTIONS = ("approval:read", "approval:create", "approval:decide", "approval:cancel")


def auth_headers(workspace_id="ws_1", user_id="usr_admin", actions=ALL_ACTIONS):
    return {
        "X-Auth-Workspace-Id": workspace_id,
        "X-Auth-User-Id": user_id,
        "X-Auth-Actions": ",".join(actions),
    }


def create_payload(**overrides):
    payload = {
        "sourceType": "publication",
        "sourceId": "pub_123",
        "title": "Instagram reel draft",
        "description": "Needs final approval",
        "reviewerUserIds": ["usr_1", "usr_2"],
    }
    payload.update(overrides)
    return payload
