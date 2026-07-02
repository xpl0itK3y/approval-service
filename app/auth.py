"""Local auth stub.

Real deployments would replace this with a call to an identity/session
service. For local runs and tests, the caller is expected to present three
headers that describe who they are already authorized to act as:

    X-Auth-Workspace-Id: workspace the caller is authorized for
    X-Auth-User-Id:      acting user id
    X-Auth-Actions:      comma separated list of granted actions, e.g.
                         "approval:read,approval:create,approval:decide,approval:cancel"

The service never trusts the workspace_id in the URL alone: every route
compares it against X-Auth-Workspace-Id and rejects mismatches, so a token
scoped to one workspace can never be used to read or mutate another.
"""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Path, status


@dataclass(frozen=True)
class AuthContext:
    workspace_id: str
    user_id: str
    actions: frozenset[str]

    def has_action(self, action: str) -> bool:
        return action in self.actions


def get_auth_context(
    x_auth_workspace_id: str | None = Header(default=None),
    x_auth_user_id: str | None = Header(default=None),
    x_auth_actions: str | None = Header(default=None),
) -> AuthContext:
    if not x_auth_workspace_id or not x_auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "unauthenticated",
                "message": "X-Auth-Workspace-Id and X-Auth-User-Id headers are required",
            },
        )

    actions = frozenset(
        a.strip() for a in (x_auth_actions or "").split(",") if a.strip()
    )

    return AuthContext(workspace_id=x_auth_workspace_id, user_id=x_auth_user_id, actions=actions)


def require_action(action: str):
    from fastapi import Depends

    def _dependency(
        workspace_id: str = Path(...),
        auth: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        if auth.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "workspace_mismatch",
                    "message": "Caller is not authorized for this workspace",
                },
            )
        if not auth.has_action(action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "action_not_granted",
                    "message": f"Action '{action}' is not granted to this caller",
                },
            )
        return auth

    return _dependency
