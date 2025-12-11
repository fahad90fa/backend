from app.core.supabase_client import supabase
from fastapi import HTTPException, status
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


class SubscriptionQueries:
    @staticmethod
    async def get_plans(active_only=True):
        try:
            query = supabase.table("subscription_plans").select("*")
            if active_only:
                query = query.eq("is_active", True)
            result = query.order("sort_order").execute()
            return result.data
        except Exception:
            return []

    @staticmethod
    async def get_plan_by_id(plan_id: str):
        try:
            result = supabase.table("subscription_plans").select("*").eq("id", plan_id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Plan not found")
            return result.data[0]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Plan not found")

    @staticmethod
    async def get_plan_by_slug(slug: str):
        try:
            result = supabase.table("subscription_plans").select("*").eq("slug", slug).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Plan not found")
            return result.data[0]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Plan not found")

    @staticmethod
    async def get_user_subscription(user_id: str):
        try:
            result = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").order("created_at", desc=True).limit(1).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception:
            return None

    @staticmethod
    async def get_subscription_history(user_id: str):
        try:
            result = supabase.table("subscriptions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            return result.data
        except Exception:
            return []

    @staticmethod
    async def get_subscription_by_id(subscription_id: str):
        try:
            result = supabase.table("subscriptions").select("*").eq("id", subscription_id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Subscription not found")
            return result.data[0]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Subscription not found")

    @staticmethod
    async def create_subscription(user_id: str, plan_id: str, plan_name: str, billing_cycle: str, price_paid: int, tokens_total: int):
        try:
            expires_at = datetime.utcnow() + (timedelta(days=365) if billing_cycle == "yearly" else timedelta(days=30))
            result = supabase.table("subscriptions").insert({
                "user_id": user_id,
                "plan_id": plan_id,
                "plan_name": plan_name,
                "billing_cycle": billing_cycle,
                "price_paid": price_paid,
                "tokens_total": tokens_total,
                "tokens_used": 0,
                "status": "active",
                "started_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
                "activated_by_admin": False,
            }).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    async def update_subscription(subscription_id: str, data: Dict):
        try:
            data["updated_at"] = datetime.utcnow().isoformat()
            result = supabase.table("subscriptions").update(data).eq("id", subscription_id).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    async def cancel_subscription(subscription_id: str, reason: str):
        return await SubscriptionQueries.update_subscription(subscription_id, {
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat(),
            "cancel_reason": reason
        })


class PaymentQueries:
    @staticmethod
    async def create_payment_request(user_id: str, plan_id: str, plan_name: str, billing_cycle: str, amount: int):
        try:
            profile_check = supabase.table("profiles").select("id").eq("id", user_id).execute()
            if not profile_check.data:
                supabase.table("profiles").insert({
                    "id": user_id,
                    "email": f"user-{user_id}@app.local",
                    "full_name": "User"
                }).execute()
            
            expires_at = datetime.utcnow() + timedelta(days=7)
            result = supabase.table("payment_requests").insert({
                "user_id": user_id,
                "plan_id": plan_id,
                "plan_name": plan_name,
                "billing_cycle": billing_cycle,
                "amount": amount,
                "currency": "USD",
                "status": "pending",
                "expires_at": expires_at.isoformat(),
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error creating payment request: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    async def get_payment_request(payment_id: str):
        try:
            result = supabase.table("payment_requests").select("*").eq("id", payment_id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Payment request not found")
            return result.data[0]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Payment request not found")

    @staticmethod
    async def get_user_payment_requests(user_id: str):
        try:
            result = supabase.table("payment_requests").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error fetching payment requests: {str(e)}")
            return []

    @staticmethod
    async def update_payment_request(payment_id: str, data: Dict):
        try:
            data["updated_at"] = datetime.utcnow().isoformat()
            result = supabase.table("payment_requests").update(data).eq("id", payment_id).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    async def submit_payment_proof(payment_id: str, transaction_reference: str, payment_date: str, screenshot_url: Optional[str] = None):
        return await PaymentQueries.update_payment_request(payment_id, {
            "transaction_reference": transaction_reference,
            "payment_date": payment_date,
            "payment_screenshot_url": screenshot_url,
        })

    @staticmethod
    async def get_pending_payments():
        try:
            result = supabase.table("payment_requests").select("*").eq("status", "pending").order("created_at").execute()
            return result.data
        except Exception:
            return []

    @staticmethod
    async def confirm_payment(payment_id: str, admin_notes: Optional[str] = None):
        return await PaymentQueries.update_payment_request(payment_id, {
            "status": "confirmed",
            "admin_confirmed_at": datetime.utcnow().isoformat(),
            "admin_notes": admin_notes,
        })

    @staticmethod
    async def reject_payment(payment_id: str, rejection_reason: str):
        return await PaymentQueries.update_payment_request(payment_id, {
            "status": "rejected",
            "rejection_reason": rejection_reason,
        })


class TokenQueries:
    @staticmethod
    async def get_user_tokens(user_id: str):
        try:
            result = supabase.table("profiles").select("tokens_total, tokens_used").eq("id", user_id).execute()
            if not result.data:
                return {
                    "total": 0,
                    "used": 0,
                    "available": 0
                }
            user = result.data[0]
            total = user.get("tokens_total") or 0
            used = user.get("tokens_used") or 0
            return {
                "total": total,
                "used": used,
                "available": max(0, total - used)
            }
        except HTTPException:
            raise
        except Exception as e:
            return {
                "total": 0,
                "used": 0,
                "available": 0
            }

    @staticmethod
    async def get_token_transactions(user_id: str):
        try:
            result = supabase.table("token_transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            return result.data
        except Exception:
            return []

    @staticmethod
    async def add_token_transaction(user_id: str, amount: int, transaction_type: str, reason: str, admin_notes: Optional[str] = None):
        try:
            tokens = await TokenQueries.get_user_tokens(user_id)
            balance_before = tokens["available"]
            balance_after = balance_before - amount if transaction_type == "usage" else balance_before + amount

            result = supabase.table("token_transactions").insert({
                "user_id": user_id,
                "amount": amount,
                "transaction_type": transaction_type,
                "reason": reason,
                "balance_before": balance_before,
                "balance_after": max(0, balance_after),
                "admin_notes": admin_notes,
            }).execute()

            if transaction_type == "usage":
                supabase.table("profiles").update({"tokens_used": tokens["used"] + amount}).eq("id", user_id).execute()
            else:
                supabase.table("profiles").update({"tokens_total": tokens["total"] + amount}).eq("id", user_id).execute()

            return result.data[0] if result.data else None
        except HTTPException:
            raise
        except Exception:
            return None


class BankSettingsQueries:
    @staticmethod
    async def get_bank_settings():
        try:
            result = supabase.table("bank_settings").select("*").limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    async def update_bank_settings(data: Dict):
        try:
            existing = await BankSettingsQueries.get_bank_settings()
            if existing:
                result = supabase.table("bank_settings").update(data).eq("id", existing["id"]).execute()
            else:
                result = supabase.table("bank_settings").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None


class AdminQueries:
    @staticmethod
    async def get_all_users(search: Optional[str] = None, tier: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
        try:
            query = supabase.table("profiles").select("*")
            
            if search:
                query = query.or_(f"email.ilike.%{search}%,username.ilike.%{search}%")
            if tier:
                query = query.eq("subscription_tier", tier)
            if status:
                query = query.eq("subscription_status", status)
            
            result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            return result.data
        except Exception:
            return []

    @staticmethod
    async def get_user(user_id: str):
        try:
            result = supabase.table("profiles").select("*").eq("id", user_id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="User not found")
            return result.data[0]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")

    @staticmethod
    async def update_user(user_id: str, data: Dict):
        try:
            result = supabase.table("profiles").update(data).eq("id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    async def ban_user(user_id: str, reason: str):
        return await AdminQueries.update_user(user_id, {
            "is_banned": True,
            "banned_at": datetime.utcnow().isoformat(),
            "ban_reason": reason
        })

    @staticmethod
    async def unban_user(user_id: str):
        return await AdminQueries.update_user(user_id, {
            "is_banned": False,
            "banned_at": None,
            "ban_reason": None
        })

    @staticmethod
    async def get_all_subscriptions(plan: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
        try:
            query = supabase.table("subscriptions").select("*")
            
            if plan:
                query = query.eq("plan_name", plan)
            if status:
                query = query.eq("status", status)
            
            result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            return result.data
        except Exception:
            return []

    @staticmethod
    async def get_admin_stats():
        try:
            users_result = supabase.table("profiles").select("count").execute()
            total_users = len(users_result.data) if users_result.data else 0

            subscriptions_result = supabase.table("subscriptions").select("*").eq("status", "active").execute()
            active_subs = subscriptions_result.data or []
            
            tier_counts = {"starter": 0, "pro": 0, "pro_plus": 0, "enterprise": 0}
            monthly_revenue = 0
            
            for sub in active_subs:
                plan_name = sub.get("plan_name", "").lower().replace(" ", "_")
                if plan_name in tier_counts:
                    tier_counts[plan_name] += 1
                monthly_revenue += sub.get("price_paid", 0)

            payments_result = supabase.table("payment_requests").select("*").eq("status", "pending").execute()
            pending_payments = len(payments_result.data) if payments_result.data else 0

            token_transactions = supabase.table("token_transactions").select("amount").eq("transaction_type", "usage").execute()
            token_usage = sum(t.get("amount", 0) for t in (token_transactions.data or []))

            all_subs = supabase.table("subscriptions").select("price_paid").execute()
            total_revenue = sum(s.get("price_paid", 0) for s in (all_subs.data or []))

            return {
                "total_users": total_users,
                "active_subscriptions": tier_counts,
                "pending_payments": pending_payments,
                "monthly_revenue": monthly_revenue,
                "total_revenue": total_revenue,
                "token_usage": token_usage
            }
        except Exception:
            return {
                "total_users": 0,
                "active_subscriptions": {"starter": 0, "pro": 0, "pro_plus": 0, "enterprise": 0},
                "pending_payments": 0,
                "monthly_revenue": 0,
                "total_revenue": 0,
                "token_usage": 0
            }

    @staticmethod
    async def get_all_payments(status: Optional[str] = None, user_id: Optional[str] = None, limit: int = 50, offset: int = 0):
        try:
            query = supabase.table("payment_requests").select("*")
            
            if status:
                query = query.eq("status", status)
            if user_id:
                query = query.eq("user_id", user_id)
            
            result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            return result.data
        except Exception:
            return []
