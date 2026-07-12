import re
import uuid as uuid_module
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional

# Valid user_id pattern: alphanumeric, hyphens, underscores, dots, @
USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._@-]+$")


def validate_not_empty(v: str) -> str:
    """Shared validator to ensure string fields are not empty or whitespace-only."""
    if not v or not v.strip():
        raise ValueError('Field cannot be empty')
    return v.strip()


def validate_user_id_format(v: str) -> str:
    """Validate user_id contains only safe characters."""
    if not USER_ID_PATTERN.match(v):
        raise ValueError('user_id contains invalid characters')
    return v


class ConsentCreate(BaseModel):
    user_id: str = Field(..., max_length=255)
    purpose: str = Field(..., max_length=500)
    metadata: Optional[str] = Field(None, max_length=2000)

    @field_validator('user_id', 'purpose')
    @classmethod
    def not_empty(cls, v):
        return validate_not_empty(v)

    @field_validator('user_id')
    @classmethod
    def valid_user_id(cls, v):
        return validate_user_id_format(v)


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str
    purpose: str
    granted: bool
    granted_at: datetime
    withdrawn_at: Optional[datetime]
    metadata: Optional[str] = Field(None, validation_alias="consent_metadata")


class ConsentWithdraw(BaseModel):
    user_id: str = Field(..., max_length=255)
    consent_id: str = Field(..., max_length=36)

    @field_validator('user_id', 'consent_id')
    @classmethod
    def not_empty(cls, v):
        return validate_not_empty(v)

    @field_validator('user_id')
    @classmethod
    def valid_user_id(cls, v):
        return validate_user_id_format(v)

    @field_validator('consent_id')
    @classmethod
    def valid_uuid(cls, v):
        try:
            uuid_module.UUID(v)
        except ValueError:
            raise ValueError('consent_id must be a valid UUID')
        return v


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    action: str
    timestamp: datetime
    details: Optional[str]


class WithdrawResponse(BaseModel):
    message: str
