from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import timedelta
from app.auth.auth import authenticate_user
from app.auth.jwt import create_access_token
from app.config import settings

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    
@router.post("/login", response_model=LoginResponse)
async def login_for_access_token(form_data: LoginRequest):
    """
    Authenticate an admin user and issue a JWT token.
    """
    # 1. Authenticate user credentials
    user = await authenticate_user(form_data.email, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 2. Check Role
    if user.get("role") not in ["main_admin", "sub_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Admins only",
        )
        
    # 3. Create Access Token
    access_token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    access_token = create_access_token(
        data={
            "sub": user["email"],
            "userId": str(user["_id"]), 
            "companyId": str(user.get("companyId")),
            "role": user.get("role"),
            "tokenVersion": user.get("tokenVersion", 1)
        },
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
