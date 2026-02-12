from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.utils.logger import logger

class Database:
    """
    Database connector that manages the MongoDB client using AsyncIOMotorClient.
    """
    client: AsyncIOMotorClient = None
    db = None

    async def connect(self):
        """
        Initializes the MongoDB connection pool.
        """
        try:
            # Create a new client and connect to the server
            self.client = AsyncIOMotorClient(settings.MONGODB_URI)
            self.db = self.client[settings.DB_NAME]
            
            # Send a ping to confirm a successful connection
            await self.client.admin.command('ping')
            logger.info(f"Successfully connected to MongoDB database '{settings.DB_NAME}'")
            
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise e

    async def close(self):
        """
        Closes the MongoDB connection pool.
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")
            
    async def create_indexes(self):
        """
        Creates necessary indexes on MongoDB collections.
        """
        if self.db is None:
            logger.warning("Database not connected, skipping index creation.")
            return

        try:
            # Companies: unique slug, name search
            await self.db["companies"].create_index("slug", unique=True)
            await self.db["companies"].create_index("name")
            
            # Users: unique email
            await self.db["users"].create_index("email", unique=True)
            await self.db["users"].create_index("companyId")
            
            # Feedback: companyId, createdAt for sorting, status
            await self.db["feedback"].create_index([("companyId", 1), ("createdAt", -1)])
            await self.db["feedback"].create_index("status")
            await self.db["feedback"].create_index("isDeleted")
            
            # Feedback Replies & Notes
            await self.db["feedbackReplies"].create_index("feedbackId")
            await self.db["feedbackNotes"].create_index("feedbackId")
            
            # Notifications
            await self.db["notifications"].create_index("userId")
            await self.db["notifications"].create_index([("userId", 1), ("isRead", 1)])
            
            # Settings: unique userId
            await self.db["settings"].create_index("userId", unique=True)
            
            logger.info("Database indexes created successfully.")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            
    async def ping(self) -> bool:
        """
        Tests the database connection with a server ping command.
        """
        if not self.client:
            return False
            
        try:
            await self.client.admin.command('ping')
            return True
        except Exception:
            return False

# Expose a reusable db object
db = Database()

async def get_database():
    """
    Dependency to provide the database instance.
    """
    return db.db
