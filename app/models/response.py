from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
from app.models.common import PyObjectId

class FeedbackReply(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    feedbackId: PyObjectId = Field(..., description="Link to Feedback._id")
    companyId: PyObjectId = Field(..., description="Link to Company._id")
    adminId: PyObjectId = Field(..., description="Link to User._id")
    message: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
