from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime, timezone
from typing import List, Optional, Any

from app.database import get_database
from app.auth.dependencies import get_current_admin
from app.utils.activity import log_activity
# Circular import prevention: import locally or use model definitions
from app.routes.admin_feedback import FeedbackResponse, map_feedback, get_feedback_with_details

router = APIRouter()

class ReplyCreate(BaseModel):
    feedbackId: str
    message: str

def sendReplyEmail(customerEmail: str, replyMessage: str):
    """
    Placeholder for email service.
    Requirement: Log email attempt if customer email exists.
    """
    print(f"[EMAIL LOG] Attempting to send reply to {customerEmail}")
    # In production, integrate with SendGrid/AWS SES/etc.
    return True

@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_reply(
    reply_in: ReplyCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Create a public reply to a feedback item.
    Returns the fully updated Feedback object for immediate UI sync.
    """
    if not ObjectId.is_valid(reply_in.feedbackId):
         raise HTTPException(status_code=400, detail="Invalid feedback ID")

    db = await get_database()
    admin_id = ObjectId(current_admin["userId"])
    company_id_str = current_admin.get("companyId")
    
    query = {"_id": ObjectId(reply_in.feedbackId)}
    
    if current_admin.get("role") != "main_admin":
        if not company_id_str or not ObjectId.is_valid(company_id_str):
             raise HTTPException(status_code=403, detail="Unauthorized: No company context")
        company_id = ObjectId(company_id_str)
        query["companyId"] = company_id
    else:
        # Fetch for main admin to get company id
        logging_fb = await db["feedback"].find_one({"_id": ObjectId(reply_in.feedbackId)})
        if not logging_fb:
             raise HTTPException(status_code=404, detail="Feedback not found")
        company_id = logging_fb.get("companyId")

    # 1. Verify feedback exists and belongs to company (Security Match)
    feedback = await db["feedback"].find_one(query)
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found or access denied")
        
    # 2. Insert into feedbackReplies collection
    new_reply = {
        "feedbackId": ObjectId(reply_in.feedbackId),
        "companyId": company_id,
        "adminId": admin_id,
        "message": reply_in.message,
        "createdAt": datetime.now(timezone.utc)
    }
    
    result = await db["feedbackReplies"].insert_one(new_reply)
    
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create reply")
    
    # 3. Update feedback timestamp
    await db["feedback"].update_one(
        {"_id": ObjectId(reply_in.feedbackId)},
        {"$set": {"updatedAt": datetime.now(timezone.utc)}}
    )

    # 4. Handle Email Notification (Placeholder)
    customer_email = feedback.get("email")
    if customer_email:
        sendReplyEmail(customer_email, reply_in.message)

    # 5. Log activity
    await log_activity(
        user_id=str(admin_id),
        company_id=str(company_id),
        action="REPLIED_TO_FEEDBACK",
        reference_id=reply_in.feedbackId,
        metadata={
            "reply_id": str(result.inserted_id),
            "email_sent": bool(customer_email)
        }
    )
        
    # 6. Return fully updated feedback including replies array
    full_data = await get_feedback_with_details(db, ObjectId(reply_in.feedbackId), company_id)
    return map_feedback(full_data)

@router.get("/{feedback_id}", response_model=List[Any]) # Kept for backward compatibility if needed
async def get_replies(
    feedback_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    if not ObjectId.is_valid(feedback_id):
         raise HTTPException(status_code=400, detail="Invalid feedback ID")

    db = await get_database()
    company_id = ObjectId(current_admin["companyId"])
    
    replies_cursor = db["feedbackReplies"].find({
        "feedbackId": ObjectId(feedback_id),
        "companyId": company_id
    }).sort("createdAt", 1)
    
    replies = await replies_cursor.to_list(length=100)
    
    return [
        {
            "id": str(r["_id"]),
            "feedbackId": str(r["feedbackId"]),
            "message": r["message"],
            "adminId": str(r["adminId"]),
            "createdAt": r["createdAt"]
        } for r in replies
    ]

