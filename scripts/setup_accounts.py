import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from dotenv import load_dotenv
import os
from datetime import datetime

# Load env
load_dotenv(dotenv_path="backend/.env")

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "feedbackpulse")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def setup_accounts():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    accounts = [
        {"email": "admin@gmail.com", "password": "admin123", "name": "Admin User"},
        {"email": "vamshi@gmail.com", "password": "vamshi123", "name": "Vamshi Krishna"}
    ]
    
    company_id = "amazon-in"
    
    for acc in accounts:
        email = acc["email"]
        password = acc["password"]
        name = acc["name"]
        
        password_hash = get_password_hash(password)
        
        existing = await db.users.find_one({"email": email})
        if existing:
            await db.users.update_one(
                {"email": email},
                {"$set": {
                    "passwordHash": password_hash,
                    "role": "admin",
                    "fullName": name,
                    "companyId": company_id
                }}
            )
            print(f"Updated: {email} / {password}")
        else:
            user = {
                "email": email,
                "passwordHash": password_hash,
                "fullName": name,
                "role": "admin",
                "companyId": company_id,
                "createdAt": datetime.utcnow()
            }
            await db.users.insert_one(user)
            print(f"Created: {email} / {password}")
            
    client.close()

if __name__ == "__main__":
    asyncio.run(setup_accounts())
