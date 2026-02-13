
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_user
from app.auth.jwt import get_password_hash

# PREFIX: /company/team
# AUDIENCE: Company Admins, Managers, Analysts ONLY
router = APIRouter(prefix="/company/team", tags=["Company Team"])

# --- Constants ---
ROLE_COMPANY_ADMIN = "company_admin"
ROLE_COMPANY_MANAGER = "company_manager"
ROLE_COMPANY_ANALYST = "company_analyst"
COMPANY_ROLES = [ROLE_COMPANY_ADMIN, ROLE_COMPANY_MANAGER, ROLE_COMPANY_ANALYST]

# --- Models ---
class TeamMemberResponse(BaseModel):
    id: str
    fullName: str
    email: str
    role: str
    isActive: bool
    lastLogin: Optional[str] = None
    createdAt: Optional[str] = None
    reviewsCount: Optional[int] = 0
    reviewsAssigned: Optional[int] = 0
    reviewsReplied: Optional[int] = 0
    responseRate: Optional[float] = 0.0
    avgResponseTime: Optional[str] = "N/A"

class InviteTeamMember(BaseModel):
    fullName: str
    email: EmailStr
    role: str 
    password: Optional[str] = None
    # No companyId here - determined from JWT

class UpdateTeamRole(BaseModel):
    role: str

class TeamMetrics(BaseModel):
    totalMembers: int
    onlineNow: int
    avgResponseRate: float
    totalReviews: int

# --- Helpers ---
def map_team_member(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "fullName": user.get("fullName", ""),
        "email": user.get("email", ""),
        "role": user.get("role", ROLE_COMPANY_ANALYST),
        "isActive": user.get("isActive", True),
        "lastLogin": user.get("lastLogin").isoformat() if user.get("lastLogin") else None,
        "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
        "reviewsCount": user.get("reviewsCount", 0),
        "reviewsAssigned": user.get("reviewsAssigned", 0),
        "reviewsReplied": user.get("reviewsReplied", 0),
        "responseRate": user.get("responseRate", 0.0),
        "avgResponseTime": user.get("avgResponseTime", "N/A"),
    }

# --- Dependencies ---
async def get_company_user(current_user: dict = Depends(get_current_user)):
    """
    STRICT: Only allow Company Roles.
    Block super_admin, sub_admin.
    """
    role = current_user.get("role", "")
    if role not in COMPANY_ROLES:
        raise HTTPException(
            status_code=403, 
            detail="Access restricted to Company members. Platform Admins must use Admin Console."
        )
    
    if not current_user.get("companyId"):
        raise HTTPException(status_code=403, detail="User not associated with any company")
        
    return current_user

def check_write_permission(user_role: str):
    if user_role in [ROLE_COMPANY_MANAGER, ROLE_COMPANY_ANALYST]:
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage team")

# --- Endpoints ---

@router.get("/", response_model=List[TeamMemberResponse])
async def list_company_team(
    current_user: dict = Depends(get_company_user)
):
    """
    Show ONLY company-level users for the current user's company.
    """
    db = await get_database()
    
    company_id = ObjectId(current_user["companyId"])

    pipeline = [
        {"$match": {
            "companyId": company_id,
            "isActive": True,
            "role": {"$in": COMPANY_ROLES}
        }},
        {
            "$lookup": {
                "from": "feedbackReplies",
                "let": {"uid": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$adminId", "$$uid"]}}}
                ],
                "as": "replies"
            }
        },
        {
            "$addFields": {
                "reviewsReplied": {"$size": "$replies"},
                "reviewsAssigned": 0, # Placeholder until assignment logic exists
                "avgResponseTime": "N/A"
            }
        },
        {"$sort": {"createdAt": -1}},
        {"$limit": 100}
    ]
    
    users = await db["users"].aggregate(pipeline).to_list(100)
    return [map_team_member(u) for u in users]


@router.get("/metrics", response_model=TeamMetrics)
async def get_team_metrics(current_user: dict = Depends(get_company_user)):
    db = await get_database()
    company_id = ObjectId(current_user["companyId"])
    
    # 1. Member Stats
    query_base = {"companyId": company_id, "isActive": True, "role": {"$in": COMPANY_ROLES}}
    total_members = await db["users"].count_documents(query_base)
    
    # Online Now logic
    now = datetime.now(timezone.utc)
    users = await db["users"].find(query_base).to_list(100)
    online_now = 0
    for u in users:
        last_login = u.get("lastLogin")
        if last_login:
            if last_login.tzinfo is None:
               last_login = last_login.replace(tzinfo=timezone.utc)
            if (now - last_login).total_seconds() < 600:
                online_now += 1

    # 2. Feedback Stats
    total_feedback = await db["feedback"].count_documents({"companyId": company_id})
    
    # Handled = Status != New
    handled_feedback = await db["feedback"].count_documents({
        "companyId": company_id, 
        "status": {"$ne": "New"}
    })
    
    # Replied Count (approximation for Response Rate)
    replied_ids = await db["feedbackReplies"].distinct("feedbackId", {"companyId": company_id})
    replied_count = len(replied_ids)
    
    avg_rate = (replied_count / total_feedback * 100) if total_feedback > 0 else 0.0

    return {
        "totalMembers": total_members,
        "onlineNow": online_now,
        "avgResponseRate": round(avg_rate, 1),
        "totalReviews": handled_feedback
    }


@router.post("/", response_model=TeamMemberResponse)
async def invite_team_member(
    invite: InviteTeamMember,
    current_user: dict = Depends(get_company_user)
):
    db = await get_database()
    creator_role = current_user.get("role")
    
    check_write_permission(creator_role)
    
    # Restrict creation rules
    if creator_role == ROLE_COMPANY_ADMIN:
        if invite.role == ROLE_COMPANY_ADMIN:
             raise HTTPException(status_code=403, detail="Company Admin cannot create another Company Admin")
        if invite.role not in [ROLE_COMPANY_MANAGER, ROLE_COMPANY_ANALYST]:
             raise HTTPException(status_code=403, detail="Invalid role for Company Admin to create")
    
    target_company_id = ObjectId(current_user["companyId"])

    existing = await db["users"].find_one({"email": invite.email})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    new_user = {
        "fullName": invite.fullName,
        "email": invite.email,
        "passwordHash": get_password_hash(invite.password or "Welcome123!"),
        "role": invite.role,
        "companyId": target_company_id,
        "isActive": True,
        "reviewsCount": 0,
        "responseRate": 0.0,
        "lastLogin": None,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    
    res = await db["users"].insert_one(new_user)
    new_user["_id"] = res.inserted_id
    
    return map_team_member(new_user)


@router.patch("/{member_id}/role", response_model=TeamMemberResponse)
async def update_member_role(
    member_id: str,
    update: UpdateTeamRole,
    current_user: dict = Depends(get_company_user)
):
    db = await get_database()
    updater_role = current_user.get("role")
    check_write_permission(updater_role)
    
    if update.role == ROLE_COMPANY_ADMIN:
         raise HTTPException(status_code=403, detail="Cannot promote to Company Admin")
    if update.role not in COMPANY_ROLES:
         raise HTTPException(status_code=400, detail="Invalid role")

    target_user = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")
        
    if str(target_user.get("companyId")) != str(current_user["companyId"]):
        raise HTTPException(status_code=404, detail="Member not found")
        
    if str(target_user["_id"]) == str(current_user["_id"]):
         raise HTTPException(status_code=400, detail="Cannot change your own role")

    updated = await db["users"].find_one_and_update(
        {"_id": ObjectId(member_id)},
        {"$set": {"role": update.role, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True
    )
    return map_team_member(updated)


@router.patch("/{member_id}/deactivate", response_model=TeamMemberResponse)
async def deactivate_member(
    member_id: str,
    current_user: dict = Depends(get_company_user)
):
    db = await get_database()
    updater_role = current_user.get("role")
    check_write_permission(updater_role)
    
    target_user = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")

    if str(target_user.get("companyId")) != str(current_user["companyId"]):
        raise HTTPException(status_code=404, detail="Member not found")

    if str(target_user["_id"]) == str(current_user["_id"]):
         raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    new_state = not target_user.get("isActive", True)
    
    updated = await db["users"].find_one_and_update(
        {"_id": ObjectId(member_id)},
        {"$set": {"isActive": new_state, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True
    )
    return map_team_member(updated)


@router.delete("/{member_id}")
async def delete_member(
    member_id: str,
    current_user: dict = Depends(get_company_user)
):
    db = await get_database()
    updater_role = current_user.get("role")
    check_write_permission(updater_role)
    
    target_user = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")

    if str(target_user.get("companyId")) != str(current_user["companyId"]):
        raise HTTPException(status_code=404, detail="Member not found")
        
    if target_user.get("role") == ROLE_COMPANY_ADMIN:
          raise HTTPException(status_code=403, detail="Cannot delete a Company Admin")
          
    if str(target_user["_id"]) == str(current_user["_id"]):
         raise HTTPException(status_code=400, detail="Cannot delete yourself")
         
    await db["users"].delete_one({"_id": ObjectId(member_id)})
    
    return {"message": "Member deleted successfully"}
