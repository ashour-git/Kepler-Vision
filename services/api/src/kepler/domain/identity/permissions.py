"""Permission keys and role→permission mapping.

The `Permission` enum is a stable set of `resource:action` strings.
The `ROLE_PERMISSIONS` map assigns defaults. Custom roles are out of
scope for MVP and will be added in a later sprint.
"""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    # Identity
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    APIKEY_READ = "apikey:read"
    APIKEY_WRITE = "apikey:write"
    APIKEY_REVOKE = "apikey:revoke"

    # Workspace
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_WRITE = "workspace:write"
    WORKSPACE_DELETE = "workspace:delete"
    MEMBER_READ = "member:read"
    MEMBER_INVITE = "member:invite"
    MEMBER_UPDATE = "member:update"
    MEMBER_REMOVE = "member:remove"

    # Audit
    AUDIT_READ = "audit:read"

    # Billing (placeholder for later sprints)
    BILLING_READ = "billing:read"
    BILLING_WRITE = "billing:write"


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    ANALYST = "analyst"
    VIEWER = "viewer"
    BILLING_ADMIN = "billing_admin"
    SERVICE = "service"


# Role → set of permissions. Order matters only for documentation.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(
        {
            Permission.USER_READ,
            Permission.USER_WRITE,
            Permission.APIKEY_READ,
            Permission.APIKEY_WRITE,
            Permission.APIKEY_REVOKE,
            Permission.WORKSPACE_READ,
            Permission.WORKSPACE_WRITE,
            Permission.MEMBER_READ,
            Permission.MEMBER_INVITE,
            Permission.MEMBER_UPDATE,
            Permission.MEMBER_REMOVE,
            Permission.AUDIT_READ,
        }
    ),
    Role.MEMBER: frozenset(
        {
            Permission.USER_READ,
            Permission.APIKEY_READ,
            Permission.APIKEY_WRITE,
            Permission.APIKEY_REVOKE,
            Permission.WORKSPACE_READ,
            Permission.MEMBER_READ,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.USER_READ,
            Permission.WORKSPACE_READ,
            Permission.MEMBER_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.USER_READ,
            Permission.WORKSPACE_READ,
            Permission.MEMBER_READ,
        }
    ),
    Role.BILLING_ADMIN: frozenset(
        {
            Permission.BILLING_READ,
            Permission.BILLING_WRITE,
        }
    ),
    Role.SERVICE: frozenset(
        {
            Permission.USER_READ,
            Permission.WORKSPACE_READ,
            Permission.MEMBER_READ,
        }
    ),
}


def permissions_for_roles(roles: list[Role]) -> set[Permission]:
    """Return the union of permissions for a set of roles."""
    result: set[Permission] = set()
    for role in roles:
        result.update(ROLE_PERMISSIONS.get(role, frozenset()))
    return result


__all__ = ["Permission", "Role", "ROLE_PERMISSIONS", "permissions_for_roles"]
