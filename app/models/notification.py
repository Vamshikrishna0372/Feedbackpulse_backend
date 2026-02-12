from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
from app.models.common import PyObjectId

class Notification(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    userId: PyObjectId = Field(..., description="Link to User._id")
    companyId: PyObjectId = Field(..., description="Link to Company._id")
    type: str = "feedback"
    title: str
    message: str
    referenceId: Optional[PyObjectId] = None
    isRead: bool = False
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
