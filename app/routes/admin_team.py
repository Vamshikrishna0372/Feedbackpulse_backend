
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Union
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_user
from app.auth.jwt import get_password_hash

# Tag as Admin Team Management - Platform level managing Company Teams
router = APIRouter(prefix="/admin/team", tags=["Admin Team Management"])

# --- Constants ---
ROLE_SUPER_ADMIN = "super_admin"
ROLE_SUB_ADMIN = "sub_admin"
PLATFORM_ROLES = [ROLE_SUPER_ADMIN, ROLE_SUB_ADMIN]

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
    companyId: str # Required for Platform Admin

class UpdateTeamRole(BaseModel):
    role: str

class TeamMetrics(BaseModel):
    totalMembers: int
    onlineNow: int
    avgResponseRate: float
    totalReviews: int
    
class PaginatedTeamResponse(BaseModel):
    items: List[TeamMemberResponse]
    total: int
    page: int
    limit: int
    pages: int


# --- Helper ---
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

# --- Dependency ---
async def get_platform_admin(current_user: dict = Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in PLATFORM_ROLES and role != "main_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access restricted to Platform Admins"
        )
    return current_user

# --- Endpoints ---

@router.get("/", response_model=Union[List[TeamMemberResponse], PaginatedTeamResponse])
async def list_company_team_as_admin(
    company_id: str = Query(..., description="Company ID is required for admin view"),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_platform_admin)
):
    """
    Platform Admins: List team members of a specific company.
    """
    db = await get_database()
    
    if not ObjectId.is_valid(company_id):
        raise HTTPException(status_code=400, detail="Invalid Company ID")

    match_stage = {
        "companyId": ObjectId(company_id),
        "isActive": True,
        "role": {"$in": COMPANY_ROLES}
    }
    
    if page is not None:
         total_count = await db["users"].count_documents(match_stage)
    
    pipeline = [
        {"$match": match_stage},
        {"$sort": {"createdAt": -1}},
    ]
    
    if page is not None:
         pipeline.append({"$skip": (page - 1) * limit})
         pipeline.append({"$limit": limit})
    else:
         pipeline.append({"$limit": 100})

    pipeline.extend([
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
                "reviewsAssigned": 0,
                "avgResponseTime": "N/A"
            }
        }
    ])
    
    limit_val = limit if page else 100
    users = await db["users"].aggregate(pipeline).to_list(limit_val)
    mapped_users = [map_team_member(u) for u in users]
    
    if page is not None:
        import math
        return PaginatedTeamResponse(
            items=mapped_users,
            total=total_count,
            page=page,
            limit=limit,
            pages=math.ceil(total_count / limit) if limit > 0 else 0
        )
        
    return mapped_users


@router.get("/metrics", response_model=TeamMetrics)
async def get_team_metrics_as_admin(
    company_id: str = Query(..., description="Company ID is required"),
    current_user: dict = Depends(get_platform_admin)
):
    db = await get_database()
    
    if not ObjectId.is_valid(company_id):
        return {"totalMembers": 0, "onlineNow": 0, "avgResponseRate": 0.0, "totalReviews": 0}

    # 1. Member Stats
    cid = ObjectId(company_id)
    query_base = {"companyId": cid, "isActive": True, "role": {"$in": COMPANY_ROLES}}
    
    total_members = await db["users"].count_documents(query_base)
    users = await db["users"].find(query_base).to_list(100)
    
    online_now = 0
    now = datetime.now(timezone.utc)
    for u in users:
        last_login = u.get("lastLogin")
        if last_login:
            if last_login.tzinfo is None:
               last_login = last_login.replace(tzinfo=timezone.utc)
            if (now - last_login).total_seconds() < 600:
                online_now += 1

    # 2. Feedback Stats
    total_feedback = await db["feedback"].count_documents({"companyId": cid})
    
    handled_feedback = await db["feedback"].count_documents({
        "companyId": cid, 
        "status": {"$ne": "New"}
    })
    
    replied_ids = await db["feedbackReplies"].distinct("feedbackId", {"companyId": cid})
    replied_count = len(replied_ids)
    
    avg_rate = (replied_count / total_feedback * 100) if total_feedback > 0 else 0.0

    return {
        "totalMembers": total_members,
        "onlineNow": online_now,
        "avgResponseRate": round(avg_rate, 1),
        "totalReviews": handled_feedback
    }


@router.post("/", response_model=TeamMemberResponse)
async def invite_member_as_admin(
    invite: InviteTeamMember,
    current_user: dict = Depends(get_platform_admin)
):
    db = await get_database()
    
    if invite.role not in COMPANY_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {COMPANY_ROLES}")
    
    if not invite.companyId:
        raise HTTPException(status_code=400, detail="Company ID required")

    # Verify Company
    company = await db["companies"].find_one({"_id": ObjectId(invite.companyId)})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check Email
    existing = await db["users"].find_one({"email": invite.email})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    password = invite.password or "Welcome123!"
    
    new_user = {
        "fullName": invite.fullName,
        "email": invite.email,
        "passwordHash": get_password_hash(password),
        "role": invite.role,
        "companyId": ObjectId(invite.companyId),
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
async def update_role_as_admin(
    member_id: str,
    update: UpdateTeamRole,
    current_user: dict = Depends(get_platform_admin)
):
    """
    Platform admins can update any company user's role.
    """
    db = await get_database()
    
    if update.role not in COMPANY_ROLES:
         raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {COMPANY_ROLES}")

    target_user = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")
        
    # Ensure target is a company user, not another super_admin
    if target_user.get("role") not in COMPANY_ROLES:
         raise HTTPException(status_code=403, detail="Cannot edit non-company roles via this endpoint")

    updated = await db["users"].find_one_and_update(
        {"_id": ObjectId(member_id)},
        {"$set": {"role": update.role, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True
    )
    
    return map_team_member(updated)


@router.patch("/{member_id}/deactivate", response_model=TeamMemberResponse)
async def deactivate_member_as_admin(
    member_id: str,
    current_user: dict = Depends(get_platform_admin)
):
    db = await get_database()
    
    target_user = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")

    if target_user.get("role") not in COMPANY_ROLES:
         raise HTTPException(status_code=403, detail="Cannot edit non-company roles via this endpoint")

    new_state = not target_user.get("isActive", True)
    
    updated = await db["users"].find_one_and_update(
        {"_id": ObjectId(member_id)},
        {"$set": {"isActive": new_state, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True
    )
    
    return map_team_member(updated)


@router.delete("/{member_id}")
async def delete_member_as_admin(
    member_id: str,
    current_user: dict = Depends(get_platform_admin)
):
    db = await get_database()
    
    target_user = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")
        
    if target_user.get("role") not in COMPANY_ROLES:
         raise HTTPException(status_code=403, detail="Cannot delete non-company roles via this endpoint")

    await db["users"].delete_one({"_id": ObjectId(member_id)})
    
    return {"message": "Member deleted successfully"}
