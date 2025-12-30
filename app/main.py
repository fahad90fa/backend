from fastapi import FastAPI, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import init_db
from app.core.supabase_client import supabase
from app.api.routes import auth, chat, training, modules, subscriptions, admin, chat_security
from app.security_middleware import RateLimitMiddleware, SecurityHeadersMiddleware, RequestLoggingMiddleware
import logging
from datetime import datetime

settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.middleware.auth import AuthMiddleware
from app.middleware.mac_verification import MACVerificationMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AI-powered Cybersecurity Educational Chatbot",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT == "development" else None,
)

allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]

if not any(origin.startswith("http://localhost") for origin in allowed_origins):
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8081",
    ])

# Ensure the frontend URL is in allowed_origins
if "https://cyber-scholar-ai.vercel.app" not in allowed_origins:
    allowed_origins.append("https://cyber-scholar-ai.vercel.app")

logger.info(f"=== CORS Configuration ===")
logger.info(f"Environment: {settings.ENVIRONMENT}")
logger.info(f"ALLOWED_ORIGINS config: {settings.ALLOWED_ORIGINS}")
logger.info(f"Parsed origins: {allowed_origins}")
logger.info(f"===========================")
logger.info(f"Running in {settings.ENVIRONMENT} mode")

cors_config = {
    "allow_origins": allowed_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "allow_headers": ["*"],
    "expose_headers": ["Content-Type", "Authorization"],
    "max_age": 86400,
}

from starlette.middleware.base import BaseHTTPMiddleware

class OptionsPreflightMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            origin = request.headers.get("origin", "")
            if not origin:
                origin = "*"
            else:
                origin_host = origin.replace("https://", "").replace("http://", "").split(":")[0]
                is_allowed = any(
                    o.replace("https://", "").replace("http://", "").split(":")[0] == origin_host
                    for o in allowed_origins
                )
                if not is_allowed:
                    origin = allowed_origins[0] if allowed_origins else "*"
                    logger.warning(f"CORS: Origin {request.headers.get('origin')} not in allowed list")
            
            logger.info(f"Preflight request to {request.url.path} from {origin}")
            return JSONResponse(
                status_code=200,
                content={},
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": request.headers.get("access-control-request-headers", "*"),
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Max-Age": "86400",
                }
            )
        return await call_next(request)

if settings.ENVIRONMENT == "production":
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class ProductionSecurityMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, allowed_hosts):
            super().__init__(app)
            self.allowed_hosts = allowed_hosts
        
        async def dispatch(self, request, call_next):
            if request.method == "OPTIONS":
                return await call_next(request)
            
            host = request.headers.get("host", "")
            
            def check_host_allowed(host: str, allowed: str) -> bool:
                if allowed.startswith("*"):
                    return host.endswith(allowed[2:])
                return host == allowed or host.endswith("." + allowed)
            
            is_allowed = any(check_host_allowed(host, allowed) for allowed in self.allowed_hosts)
            
            if not is_allowed:
                logger.warning(f"Blocked request from unauthorized host: {host}, allowed: {self.allowed_hosts}")
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Forbidden host"}, status_code=403)
            
            return await call_next(request)
    
    trusted_hosts = [origin.replace("http://", "").replace("https://", "") for origin in allowed_origins]
    trusted_hosts.extend([
        "backend-six-gamma-93.vercel.app",
        "*.vercel.app",
        "localhost",
        "127.0.0.1"
    ])
    logger.info(f"Trusted hosts: {trusted_hosts}")
    app.add_middleware(ProductionSecurityMiddleware, allowed_hosts=trusted_hosts)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MACVerificationMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(CORSMiddleware, **cors_config)
app.add_middleware(OptionsPreflightMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"][1:]) if len(error["loc"]) > 1 else "unknown"
        msg = error.get("msg", "Invalid value")
        errors.append({
            "field": field,
            "message": msg
        })
    
    origin = request.headers.get("origin", "*")
    allowed = [o for o in allowed_origins if origin.endswith(o.replace("https://", "").replace("http://", ""))]
    cors_origin = origin if allowed or "*" in allowed_origins else "*"
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation failed",
            "errors": errors
        },
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Referrer-Policy",
        }
    )
    
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    origin = request.headers.get("origin", "*")
    allowed = [o for o in allowed_origins if origin.endswith(o.replace("https://", "").replace("http://", ""))]
    cors_origin = origin if allowed or "*" in allowed_origins else "*"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Referrer-Policy",
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    origin = request.headers.get("origin", "*")
    allowed = [o for o in allowed_origins if origin.endswith(o.replace("https://", "").replace("http://", ""))]
    cors_origin = origin if allowed or "*" in allowed_origins else "*"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Referrer-Policy",
        }
    )





@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        logger.info(f"Application started in {settings.ENVIRONMENT} mode")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        if settings.ENVIRONMENT == "production":
            raise
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        if settings.ENVIRONMENT == "production":
            logger.error("CRITICAL: Failed to initialize database in production. Check DATABASE_URL.")
            raise


app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(training.router, prefix=settings.API_V1_STR)
app.include_router(modules.router, prefix=settings.API_V1_STR)
app.include_router(subscriptions.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(chat_security.router, prefix=settings.API_V1_STR)


@app.get("/test-db")
def test_db():
    return supabase.from_("profiles").select("id").limit(1).execute()


@app.get("/")
async def root():
    return {
        "message": "Welcome to CyberScholar AI",
        "docs": "/docs",
        "api_version": settings.API_V1_STR
    }


@app.get("/health")
async def health_check():
    from app.database import engine
    from app.core.supabase_client import supabase
    import sqlalchemy
    
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": settings.ENVIRONMENT,
    }
    
    db_status = "unknown"
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
        health["status"] = "degraded"
    
    health["database"] = {
        "status": db_status,
        "url_scheme": settings.DATABASE_URL.split("://")[0] if "://" in settings.DATABASE_URL else "unknown"
    }
    
    supabase_status = "unknown"
    try:
        if supabase and hasattr(supabase, 'auth'):
            supabase_status = "ready"
        else:
            supabase_status = "not_initialized"
            health["status"] = "degraded"
    except Exception as e:
        supabase_status = f"error: {str(e)[:50]}"
        health["status"] = "degraded"
    
    health["supabase"] = {"status": supabase_status}
    
    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
