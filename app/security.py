from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from app.config import get_settings
from sqlalchemy.orm import Session
from app.models import User
from app.database import get_db

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    
    # Try Supabase JWT Secret first (primary for Supabase auth)
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token, 
                settings.SUPABASE_JWT_SECRET, 
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            logger.debug("Token decoded successfully with SUPABASE_JWT_SECRET")
            return payload
        except JWTError as e:
            logger.debug(f"SUPABASE_JWT_SECRET decode failed: {str(e)}")
        except Exception as e:
            logger.debug(f"Error decoding with SUPABASE_JWT_SECRET: {str(e)}")
    
    # Fallback to local SECRET_KEY
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False}
        )
        logger.debug("Token decoded successfully with SECRET_KEY")
        return payload
    except JWTError as e:
        logger.debug(f"SECRET_KEY decode failed: {str(e)}")
    except Exception as e:
        logger.debug(f"Error decoding with SECRET_KEY: {str(e)}")
    
    logger.warning("Failed to decode token with configured secrets")
    return None


def get_current_user_id_from_request(request) -> Optional[str]:
    """
    Extract user_id from request headers (for middleware use).
    
    Args:
        request: FastAPI Request object
        
    Returns:
        User ID (UUID) if found and valid, None otherwise
    """
    try:
        authorization = request.headers.get("Authorization", "")
        if not authorization or not authorization.startswith("Bearer "):
            return None
        
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        
        if payload is None:
            return None
        
        user_id = payload.get("sub")
        return user_id
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.debug(f"Error extracting user_id from request: {str(e)}")
        return None


async def get_jwt_payload(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
        
    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        email = payload.get("email", "")
        if email:
            user = db.query(User).filter(User.email == email).first()
        
        if user is None:
            from app.core.supabase_client import supabase
            try:
                supabase_user = supabase.auth.get_user(token)
                if supabase_user and supabase_user.user:
                    user = User(
                        id=supabase_user.user.id,
                        email=supabase_user.user.email or "",
                        username=supabase_user.user.email.split("@")[0] if supabase_user.user.email else "user",
                        hashed_password="",
                        is_active=True
                    )
                    db.add(user)
                    try:
                        db.commit()
                        db.refresh(user)
                    except Exception:
                        db.rollback()
            except Exception:
                if email:
                    user = User(
                        id=user_id,
                        email=email,
                        username=email.split("@")[0],
                        hashed_password="",
                        is_active=True
                    )
                    db.add(user)
                    try:
                        db.commit()
                        db.refresh(user)
                    except Exception:
                        db.rollback()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found in system",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    return user


async def verify_token(token: str) -> dict:
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    return {"user_id": user_id, "payload": payload}
