"""RBAC — role-based access control.

Defines what each role can do. Permissions are checked at the API
layer via dependencies that read the authenticated user's role.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    STRATEGIST = "strategist"
    CREATIVE = "creative"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(str, Enum):
    # Workspace management
    MANAGE_WORKSPACE = "manage_workspace"
    MANAGE_BILLING = "manage_billing"
    MANAGE_MEMBERS = "manage_members"
    DELETE_WORKSPACE = "delete_workspace"

    # Content operations
    READ_ALL = "read_all"
    CREATE_OFFERS = "create_offers"
    EDIT_OFFERS = "edit_offers"
    CREATE_BRIEFS = "create_briefs"
    APPROVE_CONTENT = "approve_content"
    EDIT_PRIMERS = "edit_primers"
    EDIT_SKILLS = "edit_skills"

    # Creative operations
    GENERATE_CREATIVE = "generate_creative"
    EDIT_CREATIVE = "edit_creative"
    PUBLISH_CREATIVE = "publish_creative"

    # Analysis operations
    INGEST_PERFORMANCE = "ingest_performance"
    TRIGGER_ANALYSIS = "trigger_analysis"
    EXPORT_DATA = "export_data"

    # Knowledge base
    INGEST_KNOWLEDGE = "ingest_knowledge"
    EDIT_KNOWLEDGE = "edit_knowledge"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: set(Permission),  # All permissions
    Role.ADMIN: {
        Permission.MANAGE_MEMBERS, Permission.READ_ALL,
        Permission.CREATE_OFFERS, Permission.EDIT_OFFERS,
        Permission.CREATE_BRIEFS, Permission.APPROVE_CONTENT,
        Permission.EDIT_PRIMERS, Permission.EDIT_SKILLS,
        Permission.GENERATE_CREATIVE, Permission.EDIT_CREATIVE,
        Permission.PUBLISH_CREATIVE,
        Permission.INGEST_PERFORMANCE, Permission.TRIGGER_ANALYSIS,
        Permission.EXPORT_DATA,
        Permission.INGEST_KNOWLEDGE, Permission.EDIT_KNOWLEDGE,
    },
    Role.STRATEGIST: {
        Permission.READ_ALL,
        Permission.CREATE_OFFERS, Permission.EDIT_OFFERS,
        Permission.CREATE_BRIEFS, Permission.APPROVE_CONTENT,
        Permission.EDIT_PRIMERS, Permission.EDIT_SKILLS,
        Permission.GENERATE_CREATIVE, Permission.EDIT_CREATIVE,
        Permission.TRIGGER_ANALYSIS,
        Permission.INGEST_KNOWLEDGE, Permission.EDIT_KNOWLEDGE,
    },
    Role.CREATIVE: {
        Permission.READ_ALL,
        Permission.CREATE_BRIEFS,
        Permission.GENERATE_CREATIVE, Permission.EDIT_CREATIVE,
    },
    Role.ANALYST: {
        Permission.READ_ALL,
        Permission.INGEST_PERFORMANCE, Permission.TRIGGER_ANALYSIS,
        Permission.EXPORT_DATA,
    },
    Role.VIEWER: {
        Permission.READ_ALL,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    try:
        return permission in ROLE_PERMISSIONS.get(Role(role), set())
    except ValueError:
        return False
