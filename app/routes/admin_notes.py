from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime, timezone
from typing import List, Any

from app.database import get_database
from app.auth.dependencies import get_current_admin
from app.utils.activity import log_activity
from app.routes.admin_feedback import FeedbackResponse, map_feedback, get_feedback_with_details

router = APIRouter()

class NoteCreate(BaseModel):
    feedbackId: str
    note: str

@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note_in: NoteCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Create an internal note for a feedback item.
    Returns fully updated feedback for UI sync.
    """
    if not ObjectId.is_valid(note_in.feedbackId):
         raise HTTPException(status_code=400, detail="Invalid feedback ID")

    db = await get_database()
    admin_id = ObjectId(current_admin["userId"])
    company_id_str = current_admin.get("companyId")
    
    query = {"_id": ObjectId(note_in.feedbackId)}
    
    if current_admin.get("role") != "main_admin":
        if not company_id_str or not ObjectId.is_valid(company_id_str):
             raise HTTPException(status_code=403, detail="Unauthorized: No company context")
        company_id = ObjectId(company_id_str)
        query["companyId"] = company_id
    else:
        # Fetch for main admin to get company id
        logging_fb = await db["feedback"].find_one({"_id": ObjectId(note_in.feedbackId)})
        if not logging_fb:
             raise HTTPException(status_code=404, detail="Feedback not found")
        company_id = logging_fb.get("companyId")
    
    # Verify feedback exists
    feedback = await db["feedback"].find_one(query)
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found or access denied")
        
    new_note = {
        "feedbackId": ObjectId(note_in.feedbackId),
        "companyId": company_id,
        "adminId": admin_id,
        "note": note_in.note,
        "createdAt": datetime.now(timezone.utc)
    }
    
    result = await db["feedbackNotes"].insert_one(new_note)
    
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create note")
        
    # Update feedback timestamp
    await db["feedback"].update_one(
        {"_id": ObjectId(note_in.feedbackId)},
        {"$set": {"updatedAt": datetime.now(timezone.utc)}}
    )

    # Log activity
    await log_activity(
        user_id=str(admin_id),
        company_id=str(company_id),
        action="ADDED_NOTE",
        reference_id=note_in.feedbackId,
        metadata={"note_id": str(result.inserted_id)}
    )

    full_data = await get_feedback_with_details(db, ObjectId(note_in.feedbackId), company_id)
    return map_feedback(full_data)

@router.get("/{feedback_id}", response_model=List[Any])
async def get_notes(
    feedback_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    if not ObjectId.is_valid(feedback_id):
         raise HTTPException(status_code=400, detail="Invalid feedback ID")

    db = await get_database()
    company_id = ObjectId(current_admin["companyId"])
    
    notes_cursor = db["feedbackNotes"].find({
        "feedbackId": ObjectId(feedback_id),
        "companyId": company_id
    }).sort("createdAt", 1)
    
    notes = await notes_cursor.to_list(length=100)
    
    return [
        {
            "id": str(r["_id"]),
            "feedbackId": str(r["feedbackId"]),
            "note": r["note"],
            "adminId": str(r["adminId"]),
            "createdAt": r["createdAt"]
        } for r in notes
    ]

