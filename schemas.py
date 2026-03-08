from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional

class ConsentCreate(BaseModel):
    user_id: str
    purpose: str
    metadata: Optional[str] = None
    
    @field_validator('user_id', 'purpose')
    @classmethod
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()

class ConsentResponse(BaseModel):
    id: str
    user_id: str
    purpose: str
    granted: bool
    granted_at: datetime
    withdrawn_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ConsentWithdraw(BaseModel):
    user_id: str
    consent_id: str
    
    @field_validator('user_id', 'consent_id')
    @classmethod
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
