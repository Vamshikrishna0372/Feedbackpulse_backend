from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
from app.models.common import PyObjectId

class Feedback(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    companyId: PyObjectId = Field(..., description="Link to Company._id")
    rating: int = Field(..., ge=1, le=5)
    category: str
    message: str = Field(..., min_length=5)
    name: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = "Web"
    voiceTranscript: Optional[str] = None
    status: str = "New"
    priority: str = "normal"
    isPinned: bool = False
    isDeleted: bool = False
    isPublic: bool = True
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
