from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from datetime import timedelta as td
from app.database import get_db
from app.models import User
from app import schemas, security
from app.config import get_settings
from app.core.supabase_client import supabase
from app.core.mac_manager import MACManager
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
    
    try:
        signup_options = {}
        if settings.FRONTEND_URL:
            signup_options["email_redirect_to"] = f"{settings.FRONTEND_URL}/verify-email"
            
        supabase_user = supabase.auth.sign_up({
            "email": user_data.email.lower(),
            "password": user_data.password,
            "options": signup_options
        })
        
        if not supabase_user.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is already registered"
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
                detail="This username is already taken"
            )
        
        hashed_password = security.get_password_hash(user_data.password)
        
        
        new_user = User(
            id=supabase_user.user.id,
            email=user_data.email.lower(),
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=True
        )
        
        db.add(new_user)
        try:
            db.commit()
            db.refresh(new_user)
        except Exception as db_error:
            db.rollback()
        
        access_token = supabase_user.session.access_token if supabase_user.session else security.create_access_token(data={"sub": new_user.id})
        
        mac_binding = await MACManager.capture_and_bind_mac(new_user.id)
        if not mac_binding:
            logger.warning(f"MAC capture failed for new user {new_user.id}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "is_active": new_user.is_active,
                "is_verified": new_user.is_verified,
                "created_at": new_user.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed"
        )


@router.post("/login", response_model=schemas.TokenResponse)
async def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    if not EmailValidator.validate_email(credentials.email):
        logger.warning(f"Login attempt with invalid email format: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    try:
        supabase_user = supabase.auth.sign_in_with_password({
            "email": credentials.email.lower(),
            "password": credentials.password
        })
        
        if not supabase_user.user or not supabase_user.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        user = db.query(User).filter(User.email == credentials.email.lower()).first()
        
        if not user:
            user = User(
                id=supabase_user.user.id,
                email=credentials.email.lower(),
                username=credentials.email.lower().split("@")[0],
                hashed_password=security.get_password_hash(credentials.password),
                is_active=True
            )
            db.add(user)
            try:
                db.commit()
                db.refresh(user)
            except Exception as db_error:
                db.rollback()
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        mac_binding = await MACManager.capture_and_bind_mac(user.id)
        if not mac_binding:
            logger.warning(f"MAC capture failed for user {user.id} during login")
        
        access_token = supabase_user.session.access_token
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.get("/me", response_model=schemas.UserResponse)
async def get_me(current_user: User = Depends(security.get_current_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at
    }


@router.get("/verify-token")
async def verify_token(current_user: User = Depends(security.get_current_user)):
    return {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email
    }


@router.get("/profile")
async def get_profile(request: Request):
    try:
        user_id = request.state.user["sub"]
    except AttributeError:
        # Fallback if middleware didn't run (shouldn't happen if configured correctly)
        raise HTTPException(status_code=401, detail="Authentication required")
        
    try:
        # Use existing supabase client which is already initialized with service key
        profile = supabase.table('profiles').select('*').eq('id', user_id).execute()
        if profile.data and len(profile.data) > 0:
            return profile.data[0]
        
        raise HTTPException(status_code=404, detail="Profile not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Could not fetch profile from Supabase: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/init-profile")
async def init_profile(current_user: User = Depends(security.get_current_user)):
    try:
        profile = supabase.table('profiles').select('*').eq('id', str(current_user.id)).execute()
        if profile.data and len(profile.data) > 0:
            return {"status": "success", "message": "Profile already exists"}
        
        new_profile = {
            "id": str(current_user.id),
            "email": current_user.email,
            "subscription_tier": "free",
            "subscription_status": "active",
            "tokens_total": 20,
            "tokens_used": 0,
            "bonus_tokens": 0,
        }
        supabase.table('profiles').insert(new_profile).execute()
        return {"status": "success", "message": "Profile initialized"}
    except Exception as e:
        logger.warning(f"Profile initialization error: {str(e)}")
        return {"status": "success", "message": "Profile ready"}
