from fastapi import APIRouter, HTTPException, status
from app.models.feedback import Feedback
from app.database import get_database
from datetime import datetime, timezone
from bson import ObjectId

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_feedback(feedback: Feedback):
    """
    Submit new feedback.
    Validation is handled by the Feedback Pydantic model.
    """
    try:
        db = await get_database()
        
        # Convert model to dict, excluding unset fields to let DB generate _id
        feedback_dict = feedback.model_dump(by_alias=True, exclude_none=True)
        
        # Ensure companyId is an ObjectId (PyObjectId does this, but verify)
        if isinstance(feedback_dict.get("companyId"), str):
            feedback_dict["companyId"] = ObjectId(feedback_dict["companyId"])

        # Consistency defaults
        if "status" not in feedback_dict:
            feedback_dict["status"] = "New"
        if "priority" not in feedback_dict:
            feedback_dict["priority"] = "normal"
        if "isPinned" not in feedback_dict:
            feedback_dict["isPinned"] = False
        if "isDeleted" not in feedback_dict:
            feedback_dict["isDeleted"] = False
        
        # Timestamps
        now = datetime.now(timezone.utc)
        if "createdAt" not in feedback_dict:
            feedback_dict["createdAt"] = now
        if "updatedAt" not in feedback_dict:
            feedback_dict["updatedAt"] = now

        result = await db["feedback"].insert_one(feedback_dict)

        if result.inserted_id:
            return {
                "message": "Feedback submitted successfully",
                "id": str(result.inserted_id)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save feedback")

    except Exception as e:
        print(f"Error saving feedback: {e}")
        # If it's a validation error from Pydantic, FastAPI handles it before this.
        # This catch is for DB errors.
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
