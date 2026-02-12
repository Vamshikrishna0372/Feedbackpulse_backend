from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.models.common import PyObjectId

class Settings(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    userId: PyObjectId = Field(..., description="Link to User._id")
    companyId: PyObjectId = Field(..., description="Link to Company._id")
    theme: str = "light"
    emailNotifications: bool = True
    pushNotifications: bool = False
    weeklyDigest: bool = False
    marketingEmails: bool = False
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
