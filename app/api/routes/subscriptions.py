from fastapi import APIRouter, HTTPException, Depends, status, Header
from pydantic import BaseModel
from typing import Optional
from app.db.queries import SubscriptionQueries, PaymentQueries, TokenQueries, BankSettingsQueries
from app.security import verify_token

router = APIRouter(tags=["subscriptions"])


async def get_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
        return token
    except:
        raise HTTPException(status_code=401, detail="Invalid authorization header")


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan_id: str
    plan_name: str
    billing_cycle: str
    price_paid: int
    tokens_total: int
    tokens_used: int
    status: str
    started_at: str
    expires_at: str
    admin_notes: Optional[str] = None


class PaymentRequestCreate(BaseModel):
    plan_id: str
    billing_cycle: str


class PaymentProofSubmit(BaseModel):
    transaction_reference: str
    payment_date: str
    screenshot_url: Optional[str] = None


class TokenBalance(BaseModel):
    total: int
    used: int
    available: int


@router.get("/subscription-plans")
async def get_subscription_plans():
    plans = await SubscriptionQueries.get_plans(active_only=True)
    return plans


@router.get("/subscription-plans/{slug}")
async def get_subscription_plan(slug: str):
    plan = await SubscriptionQueries.get_plan_by_slug(slug)
    return plan


@router.get("/subscriptions/current")
async def get_current_subscription(token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    subscription = await SubscriptionQueries.get_user_subscription(user_id)
    return subscription


@router.get("/subscriptions/history")
async def get_subscription_history(token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    history = await SubscriptionQueries.get_subscription_history(user_id)
    return history


@router.post("/payment-requests")
async def create_payment_request(payload: PaymentRequestCreate, token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    plan = await SubscriptionQueries.get_plan_by_id(payload.plan_id)
    amount = plan["monthly_price"] if payload.billing_cycle == "monthly" else plan["yearly_price"]
    
    payment_request = await PaymentQueries.create_payment_request(
        user_id=user_id,
        plan_id=payload.plan_id,
        plan_name=plan["name"],
        billing_cycle=payload.billing_cycle,
        amount=amount
    )
    
    if not payment_request:
        raise HTTPException(status_code=500, detail="Failed to create payment request")
    
    return payment_request


@router.post("/payment-requests/{payment_id}/submit")
async def submit_payment_proof(payment_id: str, payload: PaymentProofSubmit, token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    payment = await PaymentQueries.get_payment_request(payment_id)
    if payment["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    updated = await PaymentQueries.submit_payment_proof(
        payment_id=payment_id,
        transaction_reference=payload.transaction_reference,
        payment_date=payload.payment_date,
        screenshot_url=payload.screenshot_url
    )
    
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to submit payment proof")
    
    return updated


@router.get("/payment-requests/user")
async def get_user_payment_requests(token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    payments = await PaymentQueries.get_user_payment_requests(user_id)
    return payments


@router.get("/payment-requests/{payment_id}")
async def get_payment_request(payment_id: str, token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    payment = await PaymentQueries.get_payment_request(payment_id)
    if payment["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return payment


@router.get("/tokens/balance")
async def get_token_balance(token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    tokens = await TokenQueries.get_user_tokens(user_id)
    return tokens


@router.get("/tokens/transactions")
async def get_token_transactions(token: str = Depends(get_token_from_header)):
    auth_data = await verify_token(token)
    user_id = auth_data["user_id"]
    
    transactions = await TokenQueries.get_token_transactions(user_id)
    return transactions


@router.get("/bank-settings")
async def get_bank_settings():
    settings = await BankSettingsQueries.get_bank_settings()
    return settings or {}


@router.get("/token-packs")
async def get_token_packs():
    from app.core.supabase_client import supabase
    result = supabase.table("token_packs").select("*").eq("is_active", True).execute()
    return result.data or []
