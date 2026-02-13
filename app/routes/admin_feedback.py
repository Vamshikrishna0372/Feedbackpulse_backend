from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_admin
from app.models.feedback import Feedback
from app.utils.activity import log_activity

router = APIRouter(prefix="/admin", tags=["Admin Feedback"])

# --- Models for Input/Output ---

class ReplyResponse(BaseModel):
    id: str
    message: str
    adminId: str
    createdAt: datetime

class NoteResponse(BaseModel):
    id: str
    note: str
    adminId: str
    createdAt: datetime

class ActionHistoryItem(BaseModel):
    action: str
    author: str
    timestamp: datetime

class FeedbackResponse(BaseModel):
    id: str
    companyId: str
    rating: int
    category: str
    message: str
    status: str
    priority: str
    isPinned: bool
    isDeleted: bool
    isPublic: bool
    createdAt: datetime
    updatedAt: Optional[datetime] = None
    deletedAt: Optional[datetime] = None
    name: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = "Web"
    responses: List[ReplyResponse] = []
    notes: List[NoteResponse] = []
    actionHistory: List[ActionHistoryItem] = []

class StatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(New|In Progress|Resolved|Closed)$")

class PaginatedFeedbackResponse(BaseModel):
    items: List[FeedbackResponse]
    total: int
    page: int
    limit: int
    pages: int


# --- Helper to convert Mongo document to Pydantic model ---
def map_feedback(feedback: dict) -> FeedbackResponse:
    responses = []
    if "replies" in feedback and feedback["replies"]:
        for r in feedback["replies"]:
            responses.append(ReplyResponse(
                id=str(r["_id"]),
                message=r["message"],
                adminId=str(r["adminId"]),
                createdAt=r["createdAt"]
            ))
            
    notes = []
    if "notes" in feedback and feedback["notes"]:
        for n in feedback["notes"]:
            notes.append(NoteResponse(
                id=str(n["_id"]),
                note=n["note"],
                adminId=str(n["adminId"]),
                createdAt=n["createdAt"]
            ))

    history = []
    if "history" in feedback and feedback["history"]:
        for h in feedback["history"]:
            history.append(ActionHistoryItem(
                action=h["action"],
                author=str(h["userId"]),
                timestamp=h["createdAt"]
            ))

    return FeedbackResponse(
        id=str(feedback["_id"]),
        companyId=str(feedback["companyId"]),
        rating=feedback["rating"],
        category=feedback["category"],
        message=feedback["message"],
        status=feedback.get("status", "New"),
        priority=feedback.get("priority", "normal"),
        isPinned=feedback.get("isPinned", False),
        isDeleted=feedback.get("isDeleted", False),
        isPublic=feedback.get("isPublic", True),
        createdAt=feedback.get("createdAt", datetime.now(timezone.utc)),
        updatedAt=feedback.get("updatedAt"),
        deletedAt=feedback.get("deletedAt"),
        name=feedback.get("name"),
        email=feedback.get("email"),
        source=feedback.get("source", "Web"),
        responses=responses,
        notes=notes,
        actionHistory=history
    )

async def get_feedback_with_details(db, feedback_id: ObjectId, company_id: ObjectId):
    """ Helper to fetch a single feedback with its replies and notes join """
    pipeline = [
        {"$match": {"_id": feedback_id, "companyId": company_id}},
        {
            "$lookup": {
                "from": "feedbackReplies",
                "localField": "_id",
                "foreignField": "feedbackId",
                "as": "replies"
            }
        },
        {
            "$lookup": {
                "from": "feedbackNotes",
                "localField": "_id",
                "foreignField": "feedbackId",
                "as": "notes"
            }
        },
        {
            "$lookup": {
                "from": "activityLogs",
                "localField": "_id",
                "foreignField": "referenceId",
                "as": "history"
            }
        },
        # Sort joined arrays after lookup
        {
            "$addFields": {
                "replies": {"$sortArray": {"input": "$replies", "sortBy": {"createdAt": 1}}},
                "notes": {"$sortArray": {"input": "$notes", "sortBy": {"createdAt": 1}}},
                "history": {"$sortArray": {"input": "$history", "sortBy": {"createdAt": 1}}}
            }
        }
    ]
    cursor = db["feedback"].aggregate(pipeline)
    result = await cursor.to_list(length=1)
    return result[0] if result else None

# --- Routes ---

@router.get("/feedback", response_model=Union[List[FeedbackResponse], PaginatedFeedbackResponse])
async def list_feedback(
    status: Optional[str] = Query(None, description="Filter by status"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by rating"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: dict = Depends(get_current_admin)
):
    db = await get_database()
    company_id_str = current_admin.get("companyId")
    
    # Strict multi-tenant isolation
    if not company_id_str or company_id_str == "None":
        if current_admin.get("role") == "main_admin":
             match_stage = {}
        else:
             return []
    else:
        if not ObjectId.is_valid(company_id_str):
             raise HTTPException(status_code=400, detail="Invalid Company ID")
        match_stage = {
            "companyId": ObjectId(company_id_str)
        }
    
    if status:
        match_stage["status"] = status
    if rating:
        match_stage["rating"] = rating
    if category:
        match_stage["category"] = category

    # Optimization: Sort first
    sort_stage = {"$sort": {"isPinned": -1, "createdAt": -1}}

    # Base pipeline for data
    pipeline = [
        {"$match": match_stage},
        sort_stage
    ]

    # Handle Pagination
    if page is not None:
        total_count = await db["feedback"].count_documents(match_stage)
        skip = (page - 1) * limit
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})
    else:
        # Backward compatibility: limit 100
        pipeline.append({"$limit": 100})

    # Optimization: Lookups AFTER limit
    # Only fetch details for the items we are actually returning
    pipeline.extend([
        {
            "$lookup": {
                "from": "feedbackReplies",
                "localField": "_id",
                "foreignField": "feedbackId",
                "as": "replies"
            }
        },
        {
            "$lookup": {
                "from": "feedbackNotes",
                "localField": "_id",
                "foreignField": "feedbackId",
                "as": "notes"
            }
        },
        {
            "$lookup": {
                "from": "activityLogs",
                "localField": "_id",
                "foreignField": "referenceId",
                "as": "history"
            }
        },
        {
            "$addFields": {
                "replies": {"$sortArray": {"input": "$replies", "sortBy": {"createdAt": 1}}},
                "notes": {"$sortArray": {"input": "$notes", "sortBy": {"createdAt": 1}}},
                "history": {"$sortArray": {"input": "$history", "sortBy": {"createdAt": 1}}}
            }
        }
    ])
    
    cursor = db["feedback"].aggregate(pipeline)
    feedbacks = await cursor.to_list(length=limit if page else 100)
    
    mapped_feedbacks = [map_feedback(f) for f in feedbacks]

    if page is not None:
        import math
        return PaginatedFeedbackResponse(
            items=mapped_feedbacks,
            total=total_count,
            page=page,
            limit=limit,
            pages=math.ceil(total_count / limit) if limit > 0 else 0
        )
    
    return mapped_feedbacks

@router.patch("/feedback/{feedback_id}/status", response_model=FeedbackResponse)
async def update_feedback_status(
    feedback_id: str,
    status_update: StatusUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
        
    db = await get_database()
    
    # FIX: Handle main_admin or users without specific company context
    query = {"_id": ObjectId(feedback_id)}
    company_id_str = current_admin.get("companyId")
    
    # If not main_admin, strictly enforce company isolation
    if current_admin.get("role") != "main_admin":
         if not company_id_str or not ObjectId.is_valid(company_id_str):
              raise HTTPException(status_code=403, detail="Unauthorized: No company context")
         query["companyId"] = ObjectId(company_id_str)
         # Also set company_id for logging/downstream use
         company_id = ObjectId(company_id_str)
    else:
         # For main_admin, we might need company_id for logging. Retrieve it from the feedback if needed.
         # But first let's just find and update.
         # We'll fetch the feedback first to get the companyId for the log.
         existing = await db["feedback"].find_one({"_id": ObjectId(feedback_id)})
         if not existing:
             raise HTTPException(status_code=404, detail="Feedback not found")
         company_id = existing.get("companyId")

    updated_feedback = await db["feedback"].find_one_and_update(
        query,
        {"$set": {
            "status": status_update.status,
            "updatedAt": datetime.now(timezone.utc)
        }},
        return_document=True
    )
    
    if not updated_feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    await log_activity(
        user_id=current_admin["userId"],
        company_id=str(company_id),
        action="UPDATED_STATUS",
        reference_id=feedback_id,
        metadata={"new_status": status_update.status}
    )

    # Fetch updated with details for frontend sync
    full_data = await get_feedback_with_details(db, ObjectId(feedback_id), company_id)
    return map_feedback(full_data)

@router.delete("/feedback/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(
    feedback_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """ 
    Hard delete: Permanently removes feedback and related data.
    """
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
        
    db = await get_database()
    
    query = {"_id": ObjectId(feedback_id)}
    company_id_str = current_admin.get("companyId")
    
    if current_admin.get("role") != "main_admin":
         if not company_id_str or not ObjectId.is_valid(company_id_str):
              raise HTTPException(status_code=403, detail="Unauthorized: No company context")
         query["companyId"] = ObjectId(company_id_str)
         company_id = ObjectId(company_id_str)
    else:
         existing = await db["feedback"].find_one({"_id": ObjectId(feedback_id)})
         if not existing:
             raise HTTPException(status_code=404, detail="Feedback not found")
         company_id = existing.get("companyId")
    
    # HARD DELETE
    result = await db["feedback"].delete_one(query)
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    # Cleanup related data (Replies and Notes)
    await db["feedbackReplies"].delete_many({"feedbackId": ObjectId(feedback_id)})
    await db["feedbackNotes"].delete_many({"feedbackId": ObjectId(feedback_id)})
    
    await log_activity(
        user_id=current_admin["userId"],
        company_id=str(company_id),
        action="DELETED_FEEDBACK_PERMANENTLY",
        reference_id=feedback_id
    )
    return None

# For backward compatibility or if some UI parts still use PATCH
@router.patch("/feedback/{feedback_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback_legacy_patch(feedback_id: str, current_admin: dict = Depends(get_current_admin)):
    return await delete_feedback(feedback_id, current_admin)

@router.patch("/feedback/{feedback_id}/pin", response_model=FeedbackResponse)
async def pin_feedback(
    feedback_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
        
    db = await get_database()
    
    query = {"_id": ObjectId(feedback_id)}
    company_id_str = current_admin.get("companyId")
    
    if current_admin.get("role") != "main_admin":
         if not company_id_str or not ObjectId.is_valid(company_id_str):
              raise HTTPException(status_code=403, detail="Unauthorized: No company context")
         query["companyId"] = ObjectId(company_id_str)
         company_id = ObjectId(company_id_str)
    else:
         existing = await db["feedback"].find_one({"_id": ObjectId(feedback_id)})
         if not existing:
             raise HTTPException(status_code=404, detail="Feedback not found")
         company_id = existing.get("companyId")
    
    updated_feedback = await db["feedback"].find_one_and_update(
        query,
        {"$set": {
            "isPinned": True,
            "updatedAt": datetime.now(timezone.utc)
        }},
        return_document=True
    )
    
    if not updated_feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    await log_activity(
        user_id=current_admin["userId"],
        company_id=str(company_id),
        action="PINNED_FEEDBACK",
        reference_id=feedback_id
    )

    full_data = await get_feedback_with_details(db, ObjectId(feedback_id), company_id)
    return map_feedback(full_data)

@router.patch("/feedback/{feedback_id}/unpin", response_model=FeedbackResponse)
async def unpin_feedback(
    feedback_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
        
    db = await get_database()
    
    query = {"_id": ObjectId(feedback_id)}
    company_id_str = current_admin.get("companyId")
    
    if current_admin.get("role") != "main_admin":
         if not company_id_str or not ObjectId.is_valid(company_id_str):
              raise HTTPException(status_code=403, detail="Unauthorized: No company context")
         query["companyId"] = ObjectId(company_id_str)
         company_id = ObjectId(company_id_str)
    else:
         existing = await db["feedback"].find_one({"_id": ObjectId(feedback_id)})
         if not existing:
             raise HTTPException(status_code=404, detail="Feedback not found")
         company_id = existing.get("companyId")
    
    updated_feedback = await db["feedback"].find_one_and_update(
        query,
        {"$set": {
            "isPinned": False,
            "updatedAt": datetime.now(timezone.utc)
        }},
        return_document=True
    )
    
    if not updated_feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    await log_activity(
        user_id=current_admin["userId"],
        company_id=str(company_id),
        action="UNPINNED_FEEDBACK",
        reference_id=feedback_id
    )

    full_data = await get_feedback_with_details(db, ObjectId(feedback_id), company_id)
    return map_feedback(full_data)

