import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv(dotenv_path="backend/.env")

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "feedbackpulse")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def create_admin():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    admin_email = "admin@gmail.com"
    password = "admin123"
    company_id = "amazon-in"
    
    existing_user = await db.users.find_one({"email": admin_email})
    
    password_hash = get_password_hash(password)
    
    if existing_user:
        await db.users.update_one(
            {"email": admin_email}, 
            {"$set": {"passwordHash": password_hash, "role": "admin", "companyId": company_id}}
        )
        print(f"User {admin_email} updated with password: {password}")
    else:
        admin_user = {
            "email": admin_email,
            "passwordHash": password_hash,
            "fullName": "Admin User",
            "role": "admin",
            "companyId": company_id,
            "createdAt": datetime.utcnow()
        }
        await db.users.insert_one(admin_user)
        print(f"Admin user created: {admin_email} / {password}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_admin())
