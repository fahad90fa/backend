from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from datetime import timedelta as td
from app.database import get_db
from app.models import User
from app import schemas, security
from app.config import get_settings
from app.core.supabase_client import supabase
from app.validators import (
    EmailValidator, UsernameValidator, PasswordValidator, 
    InputSanitizer, ValidatedUserCreate
)
import logging

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=schemas.TokenResponse)
async def register(user_data: ValidatedUserCreate, db: Session = Depends(get_db)):
    if not EmailValidator.validate_email(user_data.email):
        logger.warning(f"Invalid email format attempted: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    existing_user = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing_user:
        logger.warning(f"Duplicate registration attempt for email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account already exists"
        )
    
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        logger.warning(f"Duplicate username attempt: {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account already exists"
        )
    
    hashed_password = security.get_password_hash(user_data.password)
    
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": new_user.id},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "username": new_user.username,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at
        }
    }


@router.post("/login", response_model=schemas.TokenResponse)
async def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    if not EmailValidator.validate_email(credentials.email):
        logger.warning(f"Login attempt with invalid email format: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    user = db.query(User).filter(User.email == credentials.email.lower()).first()
    
    if not user or not security.verify_password(credentials.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.id},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_active": user.is_active,
            "created_at": user.created_at
        }
    }


@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user(current_user: User = Depends(security.get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }


@router.get("/profile")
async def get_profile(current_user: User = Depends(security.get_current_user)):
    try:
        profile = supabase.table('profiles').select('*').eq('id', str(current_user.id)).execute()
        if profile.data and len(profile.data) > 0:
            return profile.data[0]
        return {
            "id": str(current_user.id),
            "email": current_user.email,
            "subscription_tier": "free",
            "subscription_status": "active",
            "tokens_total": 20,
            "tokens_used": 0,
            "bonus_tokens": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "id": str(current_user.id),
            "email": current_user.email,
            "subscription_tier": "free",
            "subscription_status": "active",
            "tokens_total": 20,
            "tokens_used": 0,
            "bonus_tokens": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
