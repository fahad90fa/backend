from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import secrets
from datetime import datetime, timedelta
from app.database import get_db
from app.models import User, ChatSecurity
from app import security
from app.core.supabase_client import supabase

router = APIRouter(prefix="/chat-security", tags=["chat-security"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SetPasswordRequest(BaseModel):
    password: str
    hint: str | None = None
    user_id: str


class VerifyPasswordRequest(BaseModel):
    password: str
    user_id: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    user_id: str


class DisableSecurityRequest(BaseModel):
    password: str
    user_id: str


class ChatSecurityResponse(BaseModel):
    chat_security_enabled: bool
    chat_password_set_at: str | None
    chat_security_hint: str | None
    last_chat_access: str | None
    failed_chat_password_attempts: int
    chat_locked_until: str | None

    class Config:
        from_attributes = True


def is_strong_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in "!@#$%^&*()_+-=[]{}';:\"\\|,.<>/?`~" for c in password):
        return False
    return True


@router.post("/set-password")
async def set_password(
    req: SetPasswordRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not is_strong_password(req.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters with uppercase, lowercase, number, and special character",
        )

    try:
        salt = secrets.token_hex(16)
        password_hash = pwd_context.hash(req.password + salt)

        chat_security = db.query(ChatSecurity).filter(ChatSecurity.user_id == current_user.id).first()
        
        if chat_security:
            chat_security.chat_password_hash = password_hash
            chat_security.chat_password_salt = salt
            chat_security.chat_security_enabled = True
            chat_security.chat_security_hint = req.hint
            chat_security.chat_password_set_at = datetime.utcnow()
            chat_security.failed_chat_password_attempts = 0
            chat_security.chat_locked_until = None
        else:
            chat_security = ChatSecurity(
                user_id=current_user.id,
                chat_password_hash=password_hash,
                chat_password_salt=salt,
                chat_security_enabled=True,
                chat_security_hint=req.hint,
                chat_password_set_at=datetime.utcnow(),
                failed_chat_password_attempts=0,
            )
            db.add(chat_security)

        db.commit()

        try:
            supabase.table("profiles").update({
                "chat_security_enabled": True,
            }).eq("id", req.user_id).execute()
        except Exception as supabase_err:
            print(f"Warning: Failed to update Supabase profile: {supabase_err}")

        return {
            "success": True,
            "message": "Chat password set successfully"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set password: {str(e)}",
        )


@router.post("/verify-password")
async def verify_password(
    req: VerifyPasswordRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    try:
        chat_security = db.query(ChatSecurity).filter(ChatSecurity.user_id == current_user.id).first()
        
        if not chat_security:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat security not enabled",
            )

        if chat_security.chat_locked_until and chat_security.chat_locked_until > datetime.utcnow():
            return {
                "success": False,
                "locked": True,
                "locked_until": chat_security.chat_locked_until.isoformat(),
                "message": "Too many failed attempts. Please try again later.",
            }

        password_with_salt = req.password + chat_security.chat_password_salt
        is_valid = pwd_context.verify(password_with_salt, chat_security.chat_password_hash)

        if is_valid:
            chat_security.failed_chat_password_attempts = 0
            chat_security.chat_locked_until = None
            chat_security.last_chat_access = datetime.utcnow()
            db.commit()

            chat_session_token = secrets.token_hex(32)
            expires_at = (datetime.utcnow() + timedelta(minutes=60)).isoformat()

            return {
                "success": True,
                "message": "Access granted",
                "chatSessionToken": chat_session_token,
                "expiresAt": expires_at,
            }
        else:
            new_attempts = chat_security.failed_chat_password_attempts + 1
            lock_until = None

            if new_attempts >= 5:
                lock_until = datetime.utcnow() + timedelta(minutes=15)
            elif new_attempts >= 3:
                lock_until = datetime.utcnow() + timedelta(minutes=5)

            chat_security.failed_chat_password_attempts = new_attempts
            chat_security.chat_locked_until = lock_until
            db.commit()

            return {
                "success": False,
                "locked": lock_until is not None,
                "locked_until": lock_until.isoformat() if lock_until else None,
                "attempts_remaining": max(0, 5 - new_attempts),
                "message": "Incorrect password",
            }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify password: {str(e)}",
        )


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    try:
        chat_security = db.query(ChatSecurity).filter(ChatSecurity.user_id == current_user.id).first()
        
        if not chat_security:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat security not enabled",
            )

        password_with_salt = req.current_password + chat_security.chat_password_salt
        is_valid = pwd_context.verify(password_with_salt, chat_security.chat_password_hash)

        if not is_valid:
            return {
                "success": False,
                "message": "Current password is incorrect",
            }

        if not is_strong_password(req.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters with uppercase, lowercase, number, and special character",
            )

        new_salt = secrets.token_hex(16)
        new_hash = pwd_context.hash(req.new_password + new_salt)

        chat_security.chat_password_hash = new_hash
        chat_security.chat_password_salt = new_salt
        chat_security.chat_password_set_at = datetime.utcnow()
        db.commit()

        try:
            supabase.table("profiles").update({
                "chat_password_set_at": datetime.utcnow().isoformat(),
            }).eq("id", req.user_id).execute()
        except Exception as supabase_err:
            print(f"Warning: Failed to update Supabase profile: {supabase_err}")

        return {
            "success": True,
            "message": "Password changed successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}",
        )


@router.post("/disable-security")
async def disable_security(
    req: DisableSecurityRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    try:
        chat_security = db.query(ChatSecurity).filter(ChatSecurity.user_id == current_user.id).first()
        
        if not chat_security:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat security not enabled",
            )

        password_with_salt = req.password + chat_security.chat_password_salt
        is_valid = pwd_context.verify(password_with_salt, chat_security.chat_password_hash)

        if not is_valid:
            return {
                "success": False,
                "message": "Incorrect password",
            }

        chat_security.chat_security_enabled = False
        chat_security.chat_password_hash = None
        chat_security.chat_password_salt = None
        chat_security.chat_security_hint = None
        chat_security.chat_password_set_at = None
        chat_security.failed_chat_password_attempts = 0
        chat_security.chat_locked_until = None
        db.commit()

        try:
            supabase.table("profiles").update({
                "chat_security_enabled": False,
                "chat_password_hash": None,
                "chat_password_salt": None,
                "chat_security_hint": None,
                "chat_password_set_at": None,
            }).eq("id", req.user_id).execute()
        except Exception as supabase_err:
            print(f"Warning: Failed to update Supabase profile: {supabase_err}")

        return {
            "success": True,
            "message": "Chat security disabled",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable security: {str(e)}",
        )


@router.get("/profile", response_model=ChatSecurityResponse)
async def get_profile(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    try:
        chat_security = db.query(ChatSecurity).filter(ChatSecurity.user_id == current_user.id).first()
        
        if not chat_security:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat security profile not found",
            )
        
        return ChatSecurityResponse(
            chat_security_enabled=chat_security.chat_security_enabled,
            chat_password_set_at=chat_security.chat_password_set_at.isoformat() if chat_security.chat_password_set_at else None,
            chat_security_hint=chat_security.chat_security_hint,
            last_chat_access=chat_security.last_chat_access.isoformat() if chat_security.last_chat_access else None,
            failed_chat_password_attempts=chat_security.failed_chat_password_attempts,
            chat_locked_until=chat_security.chat_locked_until.isoformat() if chat_security.chat_locked_until else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat security profile: {str(e)}",
        )


@router.get("/log")
async def get_security_log(
    limit: int = 50,
    current_user: User = Depends(security.get_current_user),
):
    try:
        return {
            "logs": [],
            "message": "Security log feature coming soon"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch security log: {str(e)}",
        )
