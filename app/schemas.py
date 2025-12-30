from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class ChatMessageCreate(BaseModel):
    content: str
    role: str = "user"


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []
    
    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    message: ChatMessageResponse
    session_id: str
    ai_response: str


class TrainingDocumentResponse(BaseModel):
    id: str
    filename: str
    source_name: str
    file_type: str
    chunk_count: int
    checksum_sha256: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class IntegrityVerificationResponse(BaseModel):
    verified: bool
    status: str
    message: str
    checksum: Optional[str] = None


class RetrievalTestResponse(BaseModel):
    query: str
    results: List[dict]
    count: int


class TrainingChatRequest(BaseModel):
    message: str


class TrainingChatSource(BaseModel):
    filename: str
    source_name: str


class TrainingChatResponse(BaseModel):
    message_id: str
    ai_response: str
    sources: List[TrainingChatSource] = []
