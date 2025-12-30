from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt
from app.config import get_settings

settings = get_settings()

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # List of paths that require manual JWT verification via middleware
        protected_paths = [
            "/api/v1/auth/profile",
            "/api/v1/subscriptions/current", 
            "/api/v1/tokens/balance"
        ]
        
        if request.url.path in protected_paths:
            try:
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    return JSONResponse(
                        status_code=401, 
                        content={"detail": "Missing or invalid token"}
                    )
                
                token = auth_header.split(" ")[1]
                
                # Validate with Supabase JWT Secret
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    options={"verify_aud": False} # Skip audience check to be safe, or set it if known
                )
                request.state.user = payload
            except Exception as e:
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Invalid or expired token"}
                )
                
        return await call_next(request)
