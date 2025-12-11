from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.request_counts = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED or request.method == "OPTIONS":
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        now = datetime.utcnow()
        cutoff_time = now - timedelta(seconds=settings.RATE_LIMIT_PERIOD_SECONDS)
        
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if req_time > cutoff_time
        ]
        
        if len(self.request_counts[client_ip]) >= settings.RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
        
        self.request_counts[client_ip].append(now)
        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        if request.method != "OPTIONS":
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            
            if settings.ENVIRONMENT == "production":
                response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
                response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none';"
            else:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                response.headers["Content-Security-Policy"] = "default-src 'self' http://localhost:* ws://localhost:*; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' http://localhost:* ws://localhost:*; frame-ancestors 'none';"
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        
        logger.info(f"Request: {method} {path} from {client_ip}")
        
        response = await call_next(request)
        
        logger.info(f"Response: {method} {path} - Status {response.status_code}")
        
        return response
