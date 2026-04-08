from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    """Schema for creating a new role."""

    name: str = Field(min_length=1, max_length=50, description="Role name")
    permissions: dict[str, bool] = Field(
        default_factory=dict, description="Permission mapping (e.g., {'designs.create': true})"
    )


class RoleUpdate(BaseModel):
    """Schema for updating an existing role."""

    name: str | None = Field(None, min_length=1, max_length=50, description="Role name")
    permissions: dict[str, bool] | None = Field(
        None, description="Permission mapping (e.g., {'designs.create': true})"
    )


class RoleResponse(BaseModel):
    """Schema for role response."""

    id: int
    name: str
    permissions: dict[str, bool]
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserRoleAssignment(BaseModel):
    """Schema for assigning a role to a user."""

    role_id: int = Field(description="ID of the role to assign")


class UserRoleResponse(BaseModel):
    """Schema for user role assignment response."""

    id: int
    user_id: int
    role_id: int
    role_name: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
