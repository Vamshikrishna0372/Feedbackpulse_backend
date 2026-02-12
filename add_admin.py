import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from dotenv import load_dotenv
import os
from datetime import datetime
import sys

# Load environment variables
load_dotenv(dotenv_path="backend/.env")

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "feedbackpulse")

# Initialize CryptContext for password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def add_admin(email, password, name, company_id):
    if not MONGODB_URI:
        print("Error: MONGODB_URI not found in .env file")
        return

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": email})
    
    password_hash = get_password_hash(password)
    
    if existing_user:
        await db.users.update_one(
            {"email": email}, 
            {"$set": {
                "passwordHash": password_hash, 
                "role": "admin", 
                "fullName": name,
                "companyId": company_id
            }}
        )
        print(f"✅ User {email} already existed and has been UPDATED to Admin.")
    else:
        admin_user = {
            "email": email,
            "passwordHash": password_hash,
            "fullName": name,
            "role": "admin",
            "companyId": company_id,
            "createdAt": datetime.utcnow()
        }
        await db.users.insert_one(admin_user)
        print(f"✅ New Admin user created successfully: {email}")
    
    print(f"   Email: {email}")
    print(f"   Password: {password}")
    print(f"   Name: {name}")
    print(f"   Company: {company_id}")
    
    client.close()

if __name__ == "__main__":
    # You can change these values as needed
    NEW_ADMIN_EMAIL = "vamshi@gmail.com"
    NEW_ADMIN_PASS = "vamshi123"
    NEW_ADMIN_NAME = "Vamshi Krishna"
    COMPANY_ID = "amazon-in"
    
    asyncio.run(add_admin(NEW_ADMIN_EMAIL, NEW_ADMIN_PASS, NEW_ADMIN_NAME, COMPANY_ID))
