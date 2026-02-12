
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "feedbackpulse")

def generate_slug(name):
    return name.lower().replace(" ", "-").replace("&", "and").replace("'", "")

async def seed_companies():
    print("Connecting to database...")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # 1. DELETE ALL EXISTING COMPANIES
    print("WARNING: Deleting ALL existing companies...")
    await db["companies"].delete_many({})
    print("All companies deleted.")

    print(f"Preparing to seed companies...")
    
    top_companies = [
        # tech giants - global
        {"name": "Google", "industry": "Technology", "website": "https://google.com"},
        {"name": "Microsoft", "industry": "Technology", "website": "https://microsoft.com"},
        {"name": "Apple", "industry": "Technology", "website": "https://apple.com"},
        {"name": "Amazon", "industry": "E-commerce", "website": "https://amazon.com"},
        {"name": "Meta", "industry": "Technology", "website": "https://meta.com"},
        {"name": "Netflix", "industry": "Entertainment", "website": "https://netflix.com"},
        {"name": "Tesla", "industry": "Automotive", "website": "https://tesla.com"},
        {"name": "Adobe", "industry": "Technology", "website": "https://adobe.com"},
        {"name": "Salesforce", "industry": "Technology", "website": "https://salesforce.com"},
        {"name": "Oracle", "industry": "Technology", "website": "https://oracle.com"},
        {"name": "IBM", "industry": "Technology", "website": "https://ibm.com"},
        {"name": "Intel", "industry": "Technology", "website": "https://intel.com"},
        {"name": "NVIDIA", "industry": "Technology", "website": "https://nvidia.com"},
        {"name": "Cisco", "industry": "Technology", "website": "https://cisco.com"},
        {"name": "AMD", "industry": "Technology", "website": "https://amd.com"},
        {"name": "Samsung", "industry": "Electronics", "website": "https://samsung.com"},
        {"name": "Sony", "industry": "Electronics", "website": "https://sony.com"},
        {"name": "Dell Technologies", "industry": "Technology", "website": "https://dell.com"},
        {"name": "HP", "industry": "Technology", "website": "https://hp.com"},
        {"name": "SAP", "industry": "Technology", "website": "https://sap.com"},

        # major indian companies (Top 20 requested style)
        {"name": "Tata Consultancy Services", "industry": "Technology", "website": "https://tcs.com"},
        {"name": "Infosys", "industry": "Technology", "website": "https://infosys.com"},
        {"name": "Wipro", "industry": "Technology", "website": "https://wipro.com"},
        {"name": "HCL Technologies", "industry": "Technology", "website": "https://hcltech.com"},
        {"name": "Reliance Industries", "industry": "Conglomerate", "website": "https://ril.com"},
        {"name": "Jio", "industry": "Telecommunications", "website": "https://jio.com"},
        {"name": "HDFC Bank", "industry": "Finance", "website": "https://hdfcbank.com"},
        {"name": "ICICI Bank", "industry": "Finance", "website": "https://icicibank.com"},
        {"name": "State Bank of India", "industry": "Finance", "website": "https://sbi.co.in"},
        {"name": "Flipkart", "industry": "E-commerce", "website": "https://flipkart.com"},
        {"name": "Zomato", "industry": "Food Delivery", "website": "https://zomato.com"},
        {"name": "Swiggy", "industry": "Food Delivery", "website": "https://swiggy.com"},
        {"name": "Paytm", "industry": "Finance", "website": "https://paytm.com"},
        {"name": "Ola", "industry": "Transportation", "website": "https://olacabs.com"},
        {"name": "Razorpay", "industry": "Finance", "website": "https://razorpay.com"},
        {"name": "CRED", "industry": "Finance", "website": "https://cred.club"},
        {"name": "Byju's", "industry": "Education", "website": "https://byjus.com"},
        {"name": "Nykaa", "industry": "E-commerce", "website": "https://nykaa.com"},
        {"name": "Zepto", "industry": "Delivery", "website": "https://zeptonow.com"},
        {"name": "Tata Motors", "industry": "Automotive", "website": "https://tatamotors.com"},
        {"name": "Mahindra & Mahindra", "industry": "Automotive", "website": "https://mahindra.com"},
        {"name": "Bajaj Auto", "industry": "Automotive", "website": "https://bajajauto.com"},
        {"name": "Airtel", "industry": "Telecommunications", "website": "https://airtel.in"}
    ]
    
    count = 0
    for company in top_companies:
        slug = generate_slug(company["name"])
        
        # Prepare document
        doc = {
            "name": company["name"],
            "slug": slug,
            "industry": company["industry"],
            "website": company["website"],
            "description": f"Official feedback channel for {company['name']}",
            "status": "active",
            "isVerified": True,
            "isDeleted": False,
            "searchKeywords": [
                company["name"].lower(), 
                company["industry"].lower(), 
                slug.replace("-", " ")
            ],
            "updatedAt": datetime.now(timezone.utc),
            "createdAt": datetime.now(timezone.utc)
        }
        
        await db["companies"].insert_one(doc)
        count += 1
            
    print(f"Seeding complete. Added {count} new companies.")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_companies())
