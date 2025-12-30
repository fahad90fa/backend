from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import Optional
from app.db.queries import AdminQueries, SubscriptionQueries, PaymentQueries, TokenQueries, BankSettingsQueries, ContactQueries
from app.api.dependencies.admin_auth import verify_admin_token
from app.core.mac_manager import MACManager
from datetime import datetime, timedelta
from app.core.supabase_client import supabase

router = APIRouter(prefix="/admin", tags=["admin"])


class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    subscription_tier: Optional[str] = None


class BanUserRequest(BaseModel):
    reason: str


class TokenAdjustmentRequest(BaseModel):
    amount: int
    reason: str
    notes: Optional[str] = None


class SubscriptionActivateRequest(BaseModel):
    user_id: str
    plan_id: str
    billing_cycle: str


class SubscriptionExtendRequest(BaseModel):
    months: int


class SubscriptionChangePlanRequest(BaseModel):
    plan_id: str


class SubscriptionCancelRequest(BaseModel):
    reason: str


class PaymentConfirmRequest(BaseModel):
    notes: Optional[str] = None


class PaymentRejectRequest(BaseModel):
    reason: str


class PlanCreateRequest(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    monthly_price: int
    yearly_price: int
    tokens_per_month: int
    features: list = []
    is_popular: bool = False
    is_enterprise: bool = False
    sort_order: int = 0


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    monthly_price: Optional[int] = None
    yearly_price: Optional[int] = None
    tokens_per_month: Optional[int] = None
    features: Optional[list] = None
    is_popular: Optional[bool] = None
    is_active: Optional[bool] = None
    is_enterprise: Optional[bool] = None
    sort_order: Optional[int] = None


class BankSettingsUpdate(BaseModel):
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    account_number: Optional[str] = None
    iban: Optional[str] = None
    swift_bic: Optional[str] = None
    branch: Optional[str] = None
    country: Optional[str] = None
    additional_instructions: Optional[str] = None


@router.get("/stats", dependencies=[Depends(verify_admin_token)])
async def get_dashboard_stats():
    stats = await AdminQueries.get_admin_stats()
    return stats


@router.get("/users", dependencies=[Depends(verify_admin_token)])
async def list_users(
    search: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    users = await AdminQueries.get_all_users(search=search, tier=tier, status=status, limit=limit, offset=offset)
    return users


@router.get("/users/{user_id}", dependencies=[Depends(verify_admin_token)])
async def get_user(user_id: str):
    user = await AdminQueries.get_user(user_id)
    return user


@router.put("/users/{user_id}", dependencies=[Depends(verify_admin_token)])
async def update_user(user_id: str, payload: UserUpdateRequest):
    update_data = {}
    if payload.email:
        update_data["email"] = payload.email
    if payload.username:
        update_data["username"] = payload.username
    if payload.full_name:
        update_data["full_name"] = payload.full_name
    if payload.subscription_tier:
        update_data["subscription_tier"] = payload.subscription_tier
    
    user = await AdminQueries.update_user(user_id, update_data)
    return user


@router.post("/users/{user_id}/ban", dependencies=[Depends(verify_admin_token)])
async def ban_user(user_id: str, payload: BanUserRequest):
    user = await AdminQueries.ban_user(user_id, payload.reason)
    return user


@router.post("/users/{user_id}/unban", dependencies=[Depends(verify_admin_token)])
async def unban_user(user_id: str):
    user = await AdminQueries.unban_user(user_id)
    return user


@router.post("/users/{user_id}/tokens/add", dependencies=[Depends(verify_admin_token)])
async def add_tokens(user_id: str, payload: TokenAdjustmentRequest):
    await AdminQueries.get_user(user_id)
    transaction = await TokenQueries.add_token_transaction(
        user_id=user_id,
        amount=payload.amount,
        transaction_type="bonus",
        reason=payload.reason,
        admin_notes=payload.notes
    )
    return transaction


@router.post("/users/{user_id}/tokens/remove", dependencies=[Depends(verify_admin_token)])
async def remove_tokens(user_id: str, payload: TokenAdjustmentRequest):
    await AdminQueries.get_user(user_id)
    transaction = await TokenQueries.add_token_transaction(
        user_id=user_id,
        amount=payload.amount,
        transaction_type="penalty",
        reason=payload.reason,
        admin_notes=payload.notes
    )
    return transaction


@router.get("/subscriptions", dependencies=[Depends(verify_admin_token)])
async def list_subscriptions(
    plan: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    subscriptions = await AdminQueries.get_all_subscriptions(plan=plan, status=status, limit=limit, offset=offset)
    return subscriptions


@router.get("/subscriptions/{subscription_id}", dependencies=[Depends(verify_admin_token)])
async def get_subscription(subscription_id: str):
    subscription = await SubscriptionQueries.get_subscription_by_id(subscription_id)
    return subscription


@router.post("/subscriptions/activate", dependencies=[Depends(verify_admin_token)])
async def activate_subscription(payload: SubscriptionActivateRequest):
    plan = await SubscriptionQueries.get_plan_by_id(payload.plan_id)
    
    subscription = await SubscriptionQueries.create_subscription(
        user_id=payload.user_id,
        plan_id=payload.plan_id,
        plan_name=plan["name"],
        billing_cycle=payload.billing_cycle,
        price_paid=plan["monthly_price"] if payload.billing_cycle == "monthly" else plan["yearly_price"],
        tokens_total=plan["tokens_per_month"]
    )
    
    await AdminQueries.update_user(payload.user_id, {
        "subscription_tier": plan["slug"],
        "subscription_status": "active",
        "tokens_total": plan["tokens_per_month"],
        "tokens_used": 0
    })
    
    return subscription


@router.post("/subscriptions/{subscription_id}/extend", dependencies=[Depends(verify_admin_token)])
async def extend_subscription(subscription_id: str, payload: SubscriptionExtendRequest):
    subscription = await SubscriptionQueries.get_subscription_by_id(subscription_id)
    
    expires_at = datetime.fromisoformat(subscription["expires_at"])
    new_expires_at = expires_at + timedelta(days=30 * payload.months)
    
    updated = await SubscriptionQueries.update_subscription(subscription_id, {
        "expires_at": new_expires_at.isoformat()
    })
    
    return updated


@router.post("/subscriptions/{subscription_id}/change-plan", dependencies=[Depends(verify_admin_token)])
async def change_subscription_plan(subscription_id: str, payload: SubscriptionChangePlanRequest):
    subscription = await SubscriptionQueries.get_subscription_by_id(subscription_id)
    plan = await SubscriptionQueries.get_plan_by_id(payload.plan_id)
    
    updated = await SubscriptionQueries.update_subscription(subscription_id, {
        "plan_id": payload.plan_id,
        "plan_name": plan["name"],
        "tokens_total": plan["tokens_per_month"]
    })
    
    await AdminQueries.update_user(subscription["user_id"], {
        "subscription_tier": plan["slug"]
    })
    
    return updated


@router.post("/subscriptions/{subscription_id}/cancel", dependencies=[Depends(verify_admin_token)])
async def cancel_subscription(subscription_id: str, payload: SubscriptionCancelRequest):
    subscription = await SubscriptionQueries.get_subscription_by_id(subscription_id)
    
    updated = await SubscriptionQueries.cancel_subscription(subscription_id, payload.reason)
    
    await AdminQueries.update_user(subscription["user_id"], {
        "subscription_status": "cancelled"
    })
    
    return updated


@router.get("/payments", dependencies=[Depends(verify_admin_token)])
async def list_payments(
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    payments = await AdminQueries.get_all_payments(status=status, user_id=user_id, limit=limit, offset=offset)
    return payments


@router.post("/payments/{payment_id}/confirm", dependencies=[Depends(verify_admin_token)])
async def confirm_payment(payment_id: str, payload: PaymentConfirmRequest):
    try:
        # 1. Confirm the payment request
        payment = await PaymentQueries.confirm_payment(payment_id, payload.notes)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment request not found or could not be updated")
        
        # 2. Get the plan details
        try:
            plan = await SubscriptionQueries.get_plan_by_id(payment["plan_id"])
        except Exception as e:
            # If plan not found, we might want to revert the payment confirmation or just error out
            print(f"Error fetching plan {payment.get('plan_id')}: {str(e)}")
            raise HTTPException(status_code=404, detail=f"Subscription plan not found: {payment.get('plan_id')}")
        
        if not plan:
             raise HTTPException(status_code=404, detail="Subscription plan not found")

        # 3. Create the subscription
        subscription = await SubscriptionQueries.create_subscription(
            user_id=payment["user_id"],
            plan_id=payment["plan_id"],
            plan_name=payment["plan_name"],
            billing_cycle=payment["billing_cycle"],
            price_paid=payment["amount"],
            tokens_total=plan["tokens_per_month"]
        )
        
        if not subscription:
            raise HTTPException(status_code=500, detail="Failed to create subscription record")
        
        # 4. Update user profile
        profile_update = await AdminQueries.update_user(payment["user_id"], {
            "subscription_tier": plan["slug"],
            "subscription_status": "active",
            "subscription_id": subscription["id"],
            "tokens_total": plan["tokens_per_month"]
        })
        
        if not profile_update:
            print(f"Warning: Failed to update profile for user {payment['user_id']}")
            try:
                supabase.table("profiles").update({
                    "subscription_tier": plan["slug"],
                    "subscription_status": "active",
                    "subscription_id": subscription["id"],
                    "tokens_total": plan["tokens_per_month"]
                }).eq("id", payment["user_id"]).execute()
                print(f"Fallback profile update succeeded for user {payment['user_id']}")
            except Exception as e:
                print(f"Error updating profile: {str(e)}")
                # We don't raise here to avoid rolling back the payment/subscription, but we log it
        
        return payment
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unhandled error in confirm_payment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/payments/{payment_id}/reject", dependencies=[Depends(verify_admin_token)])
async def reject_payment(payment_id: str, payload: PaymentRejectRequest):
    payment = await PaymentQueries.reject_payment(payment_id, payload.reason)
    return payment


@router.get("/plans", dependencies=[Depends(verify_admin_token)])
async def list_plans():
    plans = await SubscriptionQueries.get_plans(active_only=False)
    return plans


@router.post("/plans", dependencies=[Depends(verify_admin_token)])
async def create_plan(payload: PlanCreateRequest):
    result = supabase.table("subscription_plans").insert({
        "name": payload.name,
        "slug": payload.slug,
        "description": payload.description,
        "monthly_price": payload.monthly_price,
        "yearly_price": payload.yearly_price,
        "tokens_per_month": payload.tokens_per_month,
        "features": payload.features,
        "is_popular": payload.is_popular,
        "is_enterprise": payload.is_enterprise,
        "sort_order": payload.sort_order,
        "is_active": True
    }).execute()
    return result.data[0] if result.data else None


@router.put("/plans/{plan_id}", dependencies=[Depends(verify_admin_token)])
async def update_plan(plan_id: str, payload: PlanUpdateRequest):
    update_data = {}
    if payload.name:
        update_data["name"] = payload.name
    if payload.slug:
        update_data["slug"] = payload.slug
    if payload.description is not None:
        update_data["description"] = payload.description
    if payload.monthly_price is not None:
        update_data["monthly_price"] = payload.monthly_price
    if payload.yearly_price is not None:
        update_data["yearly_price"] = payload.yearly_price
    if payload.tokens_per_month is not None:
        update_data["tokens_per_month"] = payload.tokens_per_month
    if payload.features is not None:
        update_data["features"] = payload.features
    if payload.is_popular is not None:
        update_data["is_popular"] = payload.is_popular
    if payload.is_active is not None:
        update_data["is_active"] = payload.is_active
    if payload.is_enterprise is not None:
        update_data["is_enterprise"] = payload.is_enterprise
    if payload.sort_order is not None:
        update_data["sort_order"] = payload.sort_order
    
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    result = supabase.table("subscription_plans").update(update_data).eq("id", plan_id).execute()
    return result.data[0] if result.data else None


@router.delete("/plans/{plan_id}", dependencies=[Depends(verify_admin_token)])
async def delete_plan(plan_id: str):
    await SubscriptionQueries.get_plan_by_id(plan_id)
    
    try:
        # Try to actually delete first
        result = supabase.table("subscription_plans").delete().eq("id", plan_id).execute()
        if not result.data:
            # If nothing was deleted (maybe already gone), but let's check
            return {"status": "Plan deleted"}
        return {"status": "Plan deleted"}
    except Exception as e:
        # If delete fails (likely foreign key constraint), deactivate instead
        print(f"Delete failed: {str(e)}, deactivating instead")
        supabase.table("subscription_plans").update({"is_active": False}).eq("id", plan_id).execute()
        return {"status": "Plan deactivated (in use)"}


@router.get("/token-packs", dependencies=[Depends(verify_admin_token)])
async def list_token_packs():
    result = supabase.table("token_packs").select("*").execute()
    return result.data or []


@router.post("/token-packs", dependencies=[Depends(verify_admin_token)])
async def create_token_pack(payload: dict):
    result = supabase.table("token_packs").insert(payload).execute()
    return result.data[0] if result.data else None


@router.put("/token-packs/{pack_id}", dependencies=[Depends(verify_admin_token)])
async def update_token_pack(pack_id: str, payload: dict):
    result = supabase.table("token_packs").update(payload).eq("id", pack_id).execute()
    return result.data[0] if result.data else None


@router.delete("/token-packs/{pack_id}", dependencies=[Depends(verify_admin_token)])
async def delete_token_pack(pack_id: str):
    result = supabase.table("token_packs").delete().eq("id", pack_id).execute()
    return {"success": True, "message": "Token pack deleted"}


@router.get("/settings", dependencies=[Depends(verify_admin_token)])
async def get_settings():
    settings = await BankSettingsQueries.get_bank_settings()
    return settings or {}


@router.put("/settings", dependencies=[Depends(verify_admin_token)])
async def update_settings(payload: BankSettingsUpdate):
    settings = await BankSettingsQueries.update_bank_settings(payload.dict(exclude_none=True))
    return settings


class TokenCostUpdate(BaseModel):
    cost_per_message: Optional[float] = None
    cost_per_character_response: Optional[float] = None
    enabled_per_message: Optional[bool] = None
    enabled_per_character: Optional[bool] = None


@router.get("/token-config", dependencies=[Depends(verify_admin_token)])
async def get_token_config():
    try:
        result = supabase.rpc('get_token_config').execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return {
            "cost_per_message": 1.0,
            "cost_per_character_response": 0.0,
            "enabled_per_message": True,
            "enabled_per_character": False
        }
    except Exception as e:
        print(f"Error fetching token config: {str(e)}")
        return {
            "cost_per_message": 1.0,
            "cost_per_character_response": 0.0,
            "enabled_per_message": True,
            "enabled_per_character": False
        }


@router.put("/token-config", dependencies=[Depends(verify_admin_token)])
async def update_token_config(payload: TokenCostUpdate):
    try:
        update_data = payload.dict(exclude_none=True)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        result = supabase.table("token_config").update(update_data).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return {"success": True}
    except Exception as e:
        print(f"Error updating token config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update token config: {str(e)}")


# MAC Address Management Endpoints
@router.get("/info/mac-bindings", dependencies=[Depends(verify_admin_token)])
async def get_all_mac_bindings(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get all MAC address bindings across all users"""
    try:
        response = supabase.table("mac_address_bindings").select(
            "*,profiles!inner(id,email,username)"
        ).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        if response.data:
            return {
                "count": len(response.data),
                "bindings": response.data,
                "limit": limit,
                "offset": offset
            }
        return {"count": 0, "bindings": []}
    except Exception as e:
        print(f"Error fetching MAC bindings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch MAC bindings")


@router.get("/info/mac-bindings/{user_id}", dependencies=[Depends(verify_admin_token)])
async def get_user_mac_bindings(user_id: str):
    """Get all MAC bindings for a specific user"""
    try:
        bindings = await MACManager.get_user_bindings(user_id)
        verification_log = await MACManager.get_verification_log(user_id, limit=50)
        
        return {
            "user_id": user_id,
            "bindings": bindings,
            "verification_log": verification_log
        }
    except Exception as e:
        print(f"Error fetching user MAC bindings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user MAC bindings")


@router.post("/info/mac-bindings/{binding_id}/deactivate", dependencies=[Depends(verify_admin_token)])
async def deactivate_mac_binding(binding_id: str):
    """Deactivate a MAC binding (force user to re-authenticate)"""
    try:
        success = await MACManager.deactivate_binding(binding_id)
        if success:
            return {"success": True, "message": "MAC binding deactivated. User will need to re-authenticate."}
        raise HTTPException(status_code=404, detail="MAC binding not found")
    except Exception as e:
        print(f"Error deactivating MAC binding: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to deactivate MAC binding")


@router.get("/info/mac-verification-log", dependencies=[Depends(verify_admin_token)])
async def get_mac_verification_log(
    status_filter: Optional[str] = Query(None, description="success or failed"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get MAC verification log for all users"""
    try:
        query = supabase.table("mac_verification_log").select("*").order("created_at", desc=True)
        
        if status_filter:
            query = query.eq("verification_status", status_filter)
        
        response = query.range(offset, offset + limit - 1).execute()
        
        return {
            "count": len(response.data) if response.data else 0,
            "logs": response.data or [],
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        print(f"Error fetching MAC verification log: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch verification log")


@router.get("/info/mac-stats", dependencies=[Depends(verify_admin_token)])
async def get_mac_statistics():
    """Get MAC address binding statistics"""
    try:
        bindings = supabase.table("mac_address_bindings").select("id,is_active").execute()
        verification_log = supabase.table("mac_verification_log").select("id,verification_status").execute()
        
        total_bindings = len(bindings.data) if bindings.data else 0
        active_bindings = len([b for b in (bindings.data or []) if b.get("is_active")]) if bindings.data else 0
        
        total_verifications = len(verification_log.data) if verification_log.data else 0
        successful_verifications = len([v for v in (verification_log.data or []) if v.get("verification_status") == "success"]) if verification_log.data else 0
        failed_verifications = total_verifications - successful_verifications
        
        success_rate = (successful_verifications / total_verifications * 100) if total_verifications > 0 else 0
        
        return {
            "total_bindings": total_bindings,
            "active_bindings": active_bindings,
            "inactive_bindings": total_bindings - active_bindings,
            "total_verifications": total_verifications,
            "successful_verifications": successful_verifications,
            "failed_verifications": failed_verifications,
            "success_rate_percent": round(success_rate, 2)
        }
    except Exception as e:
        print(f"Error fetching MAC statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch MAC statistics")


@router.get("/debug/mac-test", dependencies=[Depends(verify_admin_token)])
async def debug_mac_test():
    """Debug endpoint to test MAC capture functionality"""
    import platform
    from app.core.mac_sniffer import MACAddressSniffer
    from app.config import get_settings
    
    settings = get_settings()
    
    debug_info = {
        "system": platform.system(),
        "environment": settings.ENVIRONMENT,
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY),
        "supabase_url": settings.SUPABASE_URL[:50] + "..." if settings.SUPABASE_URL else "NOT SET",
        "mac_verification_key_set": bool(settings.MAC_VERIFICATION_KEY),
    }
    
    mac = MACAddressSniffer.get_system_mac()
    debug_info["mac_captured"] = mac is not None
    debug_info["mac_address"] = mac if mac else "FAILED"
    
    if mac:
        checksum = MACAddressSniffer.generate_checksum(
            mac, "test-user", settings.MAC_VERIFICATION_KEY or "default"
        )
        debug_info["checksum_generated"] = True
        debug_info["checksum_sample"] = checksum[:20] + "..."
    else:
        debug_info["checksum_generated"] = False
    
    try:
        test_response = supabase.table("mac_address_bindings").select("id").limit(1).execute()
        debug_info["supabase_accessible"] = True
        debug_info["total_bindings"] = len(test_response.data) if test_response.data else 0
    except Exception as e:
        debug_info["supabase_accessible"] = False
        debug_info["supabase_error"] = str(e)[:100]
    
    return debug_info


@router.get("/contacts", dependencies=[Depends(verify_admin_token)])
async def list_contact_requests(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    contacts = await ContactQueries.get_all_contact_requests(limit=limit, offset=offset)
    return contacts


class ContactUpdate(BaseModel):
    status: str
    admin_notes: Optional[str] = None


@router.put("/contacts/{request_id}", dependencies=[Depends(verify_admin_token)])
async def update_contact_request(request_id: str, payload: ContactUpdate):
    update_data = payload.dict()
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    result = await ContactQueries.update_contact_request(request_id, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="Contact request not found")
    return result
