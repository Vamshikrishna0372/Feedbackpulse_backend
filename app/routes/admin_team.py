from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_user, get_current_admin
from app.auth.jwt import get_password_hash

router = APIRouter(prefix="/admin/team", tags=["Admin Team"])

# --- Models ---
class TeamMemberResponse(BaseModel):
    id: str
    fullName: str
    email: str
    role: str
    isActive: bool = True
    lastLogin: Optional[str] = None
    createdAt: Optional[str] = None

class InviteTeamMember(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    role: str = "sub_admin"

class UpdateTeamMember(BaseModel):
    fullName: Optional[str] = None
    role: Optional[str] = None
    isActive: Optional[bool] = None

# --- Helper ---
def map_team_member(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "fullName": user.get("fullName", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "sub_admin"),
        "isActive": user.get("isActive", True),
        "lastLogin": user.get("lastLogin").isoformat() if user.get("lastLogin") else None,
        "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
    }

# --- Endpoints ---

@router.get("/", response_model=List[TeamMemberResponse])
async def list_team_members(current_user: dict = Depends(get_current_user)):
    """
    List all team members in the same company.
    """
    db = await get_database()
    company_id = current_user.get("companyId")
    
    query = {}
    if company_id and company_id != "None":
        query["companyId"] = ObjectId(company_id)
    
    users = await db["users"].find(query).sort("createdAt", -1).to_list(100)
    return [map_team_member(u) for u in users]


@router.post("/invite", response_model=TeamMemberResponse)
async def invite_team_member(
    invite: InviteTeamMember,
    current_user: dict = Depends(get_current_admin)
):
    """
    Invite (create) a new team member within the same company.
    """
    db = await get_database()
    
    # Check if email already exists
    existing = await db["users"].find_one({"email": invite.email})
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists")
    
    company_id = current_user.get("companyId")
    
    new_user = {
        "fullName": invite.fullName,
        "email": invite.email,
        "passwordHash": get_password_hash(invite.password),
        "role": invite.role if invite.role in ["sub_admin"] else "sub_admin",
        "companyId": ObjectId(company_id) if company_id and company_id != "None" else None,
        "isActive": True,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    
    result = await db["users"].insert_one(new_user)
    new_user["_id"] = result.inserted_id
    
    return map_team_member(new_user)


@router.patch("/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: str,
    update: UpdateTeamMember,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update a team member's details (name, role, active status).
    """
    db = await get_database()
    
    update_data = update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    # Prevent role escalation to main_admin
    if update_data.get("role") == "main_admin":
        raise HTTPException(status_code=403, detail="Cannot assign main_admin role")
    
    update_data["updatedAt"] = datetime.now(timezone.utc)
    
    updated = await db["users"].find_one_and_update(
        {"_id": ObjectId(member_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    return map_team_member(updated)


@router.delete("/{member_id}")
async def remove_team_member(
    member_id: str,
    current_user: dict = Depends(get_current_admin)
):
    """
    Soft-delete (deactivate) a team member.
    """
    db = await get_database()
    
    member = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    if member.get("role") == "main_admin":
        raise HTTPException(status_code=403, detail="Cannot remove the main admin")
    
    # Prevent self-deletion
    if str(member["_id"]) == current_user["userId"]:
        raise HTTPException(status_code=403, detail="Cannot remove yourself")
    
    await db["users"].update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"isActive": False, "updatedAt": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Team member deactivated successfully"}
