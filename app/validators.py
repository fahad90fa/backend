import re
from typing import Optional
from pydantic import field_validator, BaseModel, EmailStr
import html

class EmailValidator:
    @staticmethod
    def validate_email(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

class PasswordValidator:
    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one digit"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        return True, "Password is valid"

class UsernameValidator:
    @staticmethod
    def validate_username(username: str) -> bool:
        pattern = r'^[a-zA-Z0-9_-]{3,32}$'
        return re.match(pattern, username) is not None

class InputSanitizer:
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        if not isinstance(value, str):
            return ""
        
        value = value.strip()
        
        if len(value) > max_length:
            value = value[:max_length]
        
        value = html.escape(value)
        
        return value
    
    @staticmethod
    def sanitize_html(value: str) -> str:
        value = html.escape(value)
        return value.replace("&lt;script&gt;", "").replace("&lt;/script&gt;", "")
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        filename = re.sub(r'[^\w\s.-]', '', filename)
        filename = filename.replace("..", "")
        filename = filename.replace("/", "")
        filename = filename.replace("\\", "")
        return filename[:255]

class ValidatedUserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    
    @field_validator('username')
    def validate_username(cls, v):
        if not v:
            raise ValueError("Username is required")
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 32:
            raise ValueError("Username must not exceed 32 characters")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Username can only contain letters, numbers, underscores, or hyphens")
        return v
    
    @field_validator('password')
    def validate_password(cls, v):
        errors = []
        
        if len(v) < 8:
            errors.append("at least 8 characters")
        if not re.search(r'[A-Z]', v):
            errors.append("at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            errors.append("at least one lowercase letter")
        if not re.search(r'[0-9]', v):
            errors.append("at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            errors.append("at least one special character: !@#$%^&*()")
        
        if errors:
            msg = "Password must contain " + " and ".join(errors)
            raise ValueError(msg)
        
        return v
