from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.db.queries import ContactQueries
from datetime import datetime

router = APIRouter(prefix="/contact", tags=["contact"])

class ContactRequestCreate(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    subject: str
    message: str
    plan_slug: Optional[str] = None

@router.post("")
async def create_contact_request(payload: ContactRequestCreate):
    data = payload.dict()
    data["created_at"] = datetime.utcnow().isoformat()
    data["status"] = "pending"
    
    result = await ContactQueries.create_contact_request(data)
    
    return {"message": "Contact request submitted successfully", "id": result.get("id") if result else None}
