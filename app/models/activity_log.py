from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.models.common import PyObjectId

class ActivityLog(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    userId: PyObjectId = Field(..., description="Link to User._id")
    companyId: PyObjectId = Field(..., description="Link to Company._id")
    action: str
    referenceId: Optional[PyObjectId] = None
    metadata: Dict[str, Any] = {}
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
