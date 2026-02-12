from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_main_admin
from app.auth.jwt import get_password_hash
from app.models.user import User

router = APIRouter(prefix="/admin/management", tags=["Admin Management"])

# --- Models ---
class NewAdminRequest(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    role: str = "sub_admin" # Enforce sub_admin in logic

class AdminResponse(BaseModel):
    id: str
    fullName: str
    email: str
    role: str
    companyId: Optional[str] = None
    isActive: bool = True
    createdAt: Optional[str] = None

class UpdateAdminRequest(BaseModel):
    fullName: Optional[str] = None
    role: Optional[str] = None
    isActive: Optional[bool] = None

# --- Helper ---
def map_admin(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "fullName": user.get("fullName", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "sub_admin"),
        "companyId": str(user["companyId"]) if user.get("companyId") else None,
        "isActive": user.get("isActive", True),
        "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
    }

# --- Endpoints ---

@router.get("/admins", response_model=List[AdminResponse])
async def list_admins(current_user: dict = Depends(get_current_main_admin)):
    """
    List all admin users. Only accessible by main_admin.
    """
    db = await get_database()
    admins = await db["users"].find(
        {"role": {"$in": ["main_admin", "sub_admin"]}}
    ).sort("createdAt", -1).to_list(100)
    
    return [map_admin(a) for a in admins]


@router.post("/admins", response_model=AdminResponse)
async def create_admin(
    admin_in: NewAdminRequest,
    current_user: dict = Depends(get_current_main_admin)
):
    """
    Create a new sub_admin. Only main_admin can do this.
    """
    db = await get_database()
    
    # Prevent creating another main_admin
    if admin_in.role == "main_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create another main_admin"
        )
    
    # Check for duplicate email
    existing = await db["users"].find_one({"email": admin_in.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )
    
    new_admin = {
        "fullName": admin_in.fullName,
        "email": admin_in.email,
        "passwordHash": get_password_hash(admin_in.password),
        "role": "sub_admin",
        "companyId": ObjectId(current_user["companyId"]) if current_user.get("companyId") and current_user["companyId"] != "None" else None,
        "isActive": True,
        "tokenVersion": 1,
        "twoFactorEnabled": False,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    
    result = await db["users"].insert_one(new_admin)
    new_admin["_id"] = result.inserted_id
    
    return map_admin(new_admin)


@router.patch("/admins/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: str,
    update: UpdateAdminRequest,
    current_user: dict = Depends(get_current_main_admin)
):
    """
    Update an admin user's details. Only main_admin can do this.
    """
    db = await get_database()
    
    target = await db["users"].find_one({"_id": ObjectId(admin_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # Prevent modifying main_admin's role
    if target.get("role") == "main_admin" and update.role and update.role != "main_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change main_admin's role"
        )
    
    # Prevent role escalation
    if update.role == "main_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot promote to main_admin"
        )
    
    update_data = update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    update_data["updatedAt"] = datetime.now(timezone.utc)
    
    updated = await db["users"].find_one_and_update(
        {"_id": ObjectId(admin_id)},
        {"$set": update_data},
        return_document=True
    )
    
    return map_admin(updated)


@router.delete("/admins/{admin_id}")
async def delete_admin(
    admin_id: str,
    current_user: dict = Depends(get_current_main_admin)
):
    """
    Deactivate an admin. Only main_admin can do this. Cannot delete main_admin.
    """
    db = await get_database()
    
    target = await db["users"].find_one({"_id": ObjectId(admin_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    if target.get("role") == "main_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate the main admin"
        )
    
    # Prevent self-deletion
    if str(target["_id"]) == current_user["userId"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate yourself"
        )
    
    await db["users"].update_one(
        {"_id": ObjectId(admin_id)},
        {"$set": {"isActive": False, "updatedAt": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Admin deactivated successfully"}
