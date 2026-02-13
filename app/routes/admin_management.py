
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_user
from app.auth.jwt import get_password_hash

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

# --- Constants ---
ROLE_SUPER_ADMIN = "super_admin"
ROLE_SUB_ADMIN = "sub_admin"

# --- Helper ---
def map_admin(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "fullName": user.get("fullName", ""),
        "email": user.get("email", ""),
        "role": user.get("role", ROLE_SUB_ADMIN),
        "companyId": str(user["companyId"]) if user.get("companyId") else None,
        "isActive": user.get("isActive", True),
        "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
    }

# --- Dependency ---
async def get_super_admin(current_user: dict = Depends(get_current_user)):
    """
    Ensure the user is a super_admin (Platform Root).
    """
    role = current_user.get("role", "")
    if role != ROLE_SUPER_ADMIN and role != "main_admin": # Legacy support
        raise HTTPException(status_code=403, detail="Requires Super Admin privileges")
    return current_user

# --- Endpoints ---

@router.get("/admins", response_model=List[AdminResponse])
async def list_admins(current_user: dict = Depends(get_super_admin)):
    """
    List all platform admins (super_admin, sub_admin).
    """
    db = await get_database()
    admins = await db["users"].find(
        {"role": {"$in": [ROLE_SUPER_ADMIN, ROLE_SUB_ADMIN, "main_admin"]}}
    ).sort("createdAt", -1).to_list(100)
    
    return [map_admin(a) for a in admins]


@router.post("/admins", response_model=AdminResponse)
async def create_admin(
    admin_in: NewAdminRequest,
    current_user: dict = Depends(get_super_admin)
):
    """
    Create a new sub_admin. Only super_admin can do this.
    Platform roles must have companyId = null.
    """
    db = await get_database()
    
    # Prevent creating another super_admin via this route? 
    # Prompt says "super_admin can Create sub_admin". 
    # "sub_admin can Create company_admin".
    # Does not say sub_admin can create sub_admin.
    # Logic: Only super_admin can create sub_admin.
    
    if admin_in.role == ROLE_SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create another super_admin via this API"
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
        "role": ROLE_SUB_ADMIN,
        "companyId": None, # Platform Role
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
    current_user: dict = Depends(get_super_admin)
):
    """
    Update an admin user's details. Only super_admin can do this.
    """
    db = await get_database()
    
    target = await db["users"].find_one({"_id": ObjectId(admin_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # Prevent modifying super_admin's role (self or other) to something else easily?
    if target.get("role") == ROLE_SUPER_ADMIN:
        if update.role and update.role != ROLE_SUPER_ADMIN:
             raise HTTPException(status_code=403, detail="Cannot demote super_admin")
    
    # Prevent promotion to super_admin via this endpoint
    if update.role == ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot promote to super_admin")

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
    current_user: dict = Depends(get_super_admin)
):
    """
    Permanently delete an admin. Only super_admin can do this.
    """
    try:
        from bson import ObjectId
        if not ObjectId.is_valid(admin_id):
            raise HTTPException(status_code=400, detail="Invalid admin ID format")
            
        db = await get_database()
        target = await db["users"].find_one({"_id": ObjectId(admin_id)})
        
        if not target:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        if target.get("role") == ROLE_SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete super_admin"
            )
        
        # Prevent self-deletion
        current_admin_id = current_user.get("userId")
        if str(target["_id"]) == str(current_admin_id):
             raise HTTPException(status_code=403, detail="Cannot delete your own account")

        result = await db["users"].delete_one({"_id": ObjectId(admin_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=500, detail="Failed to delete admin")
        
        return {"message": "Admin removed permanently"}
    except HTTPException:
        raise
    except Exception as e:
        from app.utils.logger import logger
        logger.error(f"Error deleting admin {admin_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error while deleting: {str(e)}")
