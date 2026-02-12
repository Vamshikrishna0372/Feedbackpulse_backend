from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
from app.models.common import PyObjectId

class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    fullName: str
    email: str
    passwordHash: str
    role: str = "sub_admin" # Default is sub_admin, specifically main_admin or sub_admin
    companyId: Optional[PyObjectId] = Field(None, description="Link to Company._id")
    isActive: bool = True
    twoFactorEnabled: bool = False
    tokenVersion: int = 1
    lastLogin: Optional[datetime] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
