import logging
import os
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.mac_manager import MACManager

logger = logging.getLogger(__name__)

SENSITIVE_ROUTES = [
    "/api/v1/chat/",
    "/api/v1/training/",
    "/api/v1/subscriptions/",
    "/api/v1/admin/",
]

logger.info(f"MAC Verification Middleware initialized with sensitive routes: {SENSITIVE_ROUTES}")


class MACVerificationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify MAC address on sensitive requests.
    Ensures that requests come from the same device that was used during registration/login.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        
        # Bypass MAC verification in serverless environments like Vercel
        # because the system MAC address will be that of the Vercel execution environment
        # and not the user's device, which will cause verification failures.
        if os.getenv("VERCEL") == "1" or os.getenv("VERCEL"):
            logger.debug(f"Bypassing MAC verification for Vercel environment: {path}")
            return await call_next(request)
        
        if method == "OPTIONS":
            logger.debug(f"Skipping MAC verification for OPTIONS preflight: {path}")
            return await call_next(request)
        
        is_sensitive = any(path.startswith(route) for route in SENSITIVE_ROUTES)
        
        if not is_sensitive:
            logger.debug(f"Non-sensitive route [{method}]: {path}, skipping MAC verification")
            return await call_next(request)
        
        logger.info(f"Sensitive route detected [{method}]: {path}, performing MAC verification")
        
        try:
            user_id = getattr(request.state, "user_id", None)
            logger.debug(f"user_id from request.state: {user_id}")
            
            if not user_id:
                try:
                    from app.security import get_current_user_id_from_request
                    user_id = get_current_user_id_from_request(request)
                    logger.debug(f"user_id from request headers: {user_id}")
                except Exception as e:
                    logger.debug(f"Could not extract user_id from request: {str(e)}")
                    return await call_next(request)
            
            if not user_id:
                logger.debug(f"No user_id found, skipping MAC verification")
                return await call_next(request)
            
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            logger.info(f"Performing MAC verification for user {user_id}")
            verification = await MACManager.verify_mac(user_id, ip_address, user_agent)
            logger.info(f"MAC verification result for user {user_id}: {verification}")
            
            if not verification.get("verified"):
                logger.warning(
                    f"MAC verification failed for user {user_id} on {path}: {verification.get('reason')}"
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Device verification failed. Please log in again."}
                )
            
            logger.info(f"MAC verification successful for user {user_id}")
            request.state.mac_verified = True
            
        except Exception as e:
            logger.error(f"Error in MAC verification middleware: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Verification service error"}
            )
        
        return await call_next(request)
