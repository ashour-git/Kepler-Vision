"""Identity domain — pure Python, no I/O."""

from .entities import (
    ApiKey,
    ApiKeyStatus,
    Membership,
    Tenant,
    TenantPlan,
    TenantStatus,
    User,
    UserStatus,
)
from .value_objects import ApiKeyId, Email, Password, TenantId, UserId
from .permissions import Permission, Role, ROLE_PERMISSIONS, permissions_for_roles
from .events import (
    DomainEvent,
    MembershipAdded,
    MembershipRemoved,
    MembershipRoleChanged,
    TokenRefreshed,
    TokenRevoked,
    UserSignedIn,
    UserSignedOut,
    UserSignedUp,
)
from .services import (
    check_password_policy,
    compute_audit_payload,
    is_valid_tenant_slug,
    password_meets_policy,
)

__all__ = [
    "User",
    "Tenant",
    "ApiKey",
    "Membership",
    "UserStatus",
    "ApiKeyStatus",
    "TenantPlan",
    "TenantStatus",
    "Email",
    "Password",
    "UserId",
    "TenantId",
    "ApiKeyId",
    "Permission",
    "Role",
    "ROLE_PERMISSIONS",
    "permissions_for_roles",
    "DomainEvent",
    "UserSignedUp",
    "UserSignedIn",
    "UserSignedOut",
    "TokenRefreshed",
    "TokenRevoked",
    "MembershipAdded",
    "MembershipRemoved",
    "MembershipRoleChanged",
    "check_password_policy",
    "password_meets_policy",
    "is_valid_tenant_slug",
    "compute_audit_payload",
]
