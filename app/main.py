import time
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import db
from app.utils.logger import logger
from app.routes.feedback import router as feedback_router
from app.routes.auth import router as auth_router
from app.routes.admin_feedback import router as admin_feedback_router
from app.routes.admin_dashboard import router as admin_dashboard_router
from app.routes.analytics import router as analytics_router
from app.routes.admin_profile import router as admin_profile_router
from app.routes.admin_settings import router as admin_settings_router
from app.routes.admin_team import router as admin_team_router
from app.routes.companies import router as companies_router
from app.routes.admin_replies import router as admin_replies_router
from app.routes.admin_notes import router as admin_notes_router
from app.routes.admin_management import router as admin_management_router
from app.routes.user import router as user_router
from app.routes.company_team import router as company_team_router

# Track startup time for uptime calculation
START_TIME = time.time()

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["1000/hour", "50/minute"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    try:
        await db.connect()
        await db.create_indexes()
        logger.info("Application startup complete.")
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise e
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await db.close()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# --- Exception Handlers ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msg = exc.errors()[0].get('msg', 'Invalid input')
    field = exc.errors()[0].get('loc', ['unknown'])[-1]
    return JSONResponse(status_code=422, content={"error": f"{field}: {error_msg}"})

# --- Request Logging Middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
        
    start_time = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        log_msg = f"{request.method} {request.url.path} - {response.status_code} - {duration:.4f}s"
        if 200 <= response.status_code < 400:
            logger.info(log_msg)
        else:
            logger.warning(log_msg)
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)}")
        raise e

# --- Routes ---
@app.get("/health")
@limiter.exempt 
async def health_check():
    db_status = await db.ping()
    return {
        "status": "healthy" if db_status else "unhealthy",
        "uptime_seconds": int(time.time() - START_TIME),
        "database": "connected" if db_status else "disconnected"
    }

app.include_router(feedback_router, prefix="/feedback", tags=["Feedback"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(companies_router, prefix="/companies", tags=["Companies"])
app.include_router(admin_feedback_router, tags=["Admin Feedback"])
app.include_router(admin_replies_router, prefix="/admin/replies", tags=["Admin Replies"])
app.include_router(admin_notes_router, prefix="/admin/notes", tags=["Admin Notes"])
app.include_router(admin_dashboard_router, tags=["Admin Dashboard"])
app.include_router(analytics_router, tags=["Admin Analytics"])
app.include_router(admin_team_router, tags=["Admin Team"])
app.include_router(admin_management_router)
app.include_router(user_router)
app.include_router(company_team_router)
app.include_router(admin_profile_router, tags=["Admin Profile"])
app.include_router(admin_settings_router, tags=["Admin Settings"])

# --- CORS Configuration (ADDED LAST to be OUTERMOST) ---
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
] + settings.ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if settings.ENVIRONMENT == "development" else settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
