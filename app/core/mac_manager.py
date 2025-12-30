import logging
from typing import Optional, Dict
from app.core.mac_sniffer import MACAddressSniffer, MACSnifferError
from app.core.supabase_client import supabase
from app.config import get_settings
import platform

settings = get_settings()
logger = logging.getLogger(__name__)


class MACManager:
    """
    Manager for MAC address binding and verification.
    Handles capturing, storing, and verifying MAC addresses for device fingerprinting.
    """

    @staticmethod
    async def capture_and_bind_mac(user_id: str) -> Optional[Dict]:
        """
        Capture system MAC address and bind it to the user.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            Dict with mac, checksum, and device info, or None if capture failed
            
        Raises:
            HTTPException with 403 if MAC cannot be captured
        """
        try:
            logger.info(f"Starting MAC capture for user {user_id}")
            mac = MACAddressSniffer.get_system_mac()
            
            if not mac:
                logger.error(f"Failed to capture MAC for user {user_id}: No MAC address detected")
                logger.error(f"System platform: {platform.system()}, Node: {platform.node()}")
                raise MACSnifferError("Unable to capture system MAC address")
            
            secret_key = settings.MAC_VERIFICATION_KEY or "default-secret"
            checksum = MACAddressSniffer.generate_checksum(mac, user_id, secret_key)
            logger.info(f"MAC captured for user {user_id}: {mac}")
            
            device_os = platform.system()
            device_name = platform.node()
            
            try:
                try:
                    profile = supabase.table("profiles").select("id").eq("id", user_id).limit(1).execute()
                    logger.info(f"Profile lookup for user {user_id}: found={bool(profile.data)}")
                    if not profile.data:
                        logger.warning(f"Profile missing for user {user_id}, creating default profile")
                        profile_response = supabase.table("profiles").insert({
                            "id": user_id,
                            "subscription_tier": "free",
                            "subscription_status": "active",
                            "tokens_total": 20,
                            "tokens_used": 0
                        }).execute()
                        logger.info(f"Created default profile for user {user_id}: response={bool(profile_response.data)}")
                    else:
                        logger.info(f"Profile already exists for user {user_id}")
                except Exception as profile_error:
                    logger.warning(f"Could not ensure profile exists for user {user_id}: {type(profile_error).__name__}: {str(profile_error)}")
                
                existing = await MACManager.get_active_binding(user_id)
                
                if existing:
                    logger.info(f"Updating MAC binding for user {user_id}")
                    response = supabase.table("mac_address_bindings").update({
                        "mac_address": mac,
                        "mac_checksum": checksum,
                        "device_os": device_os,
                        "device_name": device_name,
                        "last_seen": "now()",
                        "is_active": True
                    }).eq("id", existing["id"]).execute()
                    logger.info(f"Update response for user {user_id}: {response.data is not None}")
                else:
                    logger.info(f"Creating new MAC binding for user {user_id}")
                    response = supabase.table("mac_address_bindings").insert({
                        "user_id": user_id,
                        "mac_address": mac,
                        "mac_checksum": checksum,
                        "device_os": device_os,
                        "device_name": device_name,
                        "is_active": True
                    }).execute()
                    logger.info(f"Insert response for user {user_id}: {response.data is not None}")
                
                if response.data:
                    binding = response.data[0]
                    logger.info(f"MAC binding successful for user {user_id}: binding_id={binding.get('id')}")
                    return {
                        "mac": mac,
                        "checksum": checksum,
                        "device_os": device_os,
                        "device_name": device_name,
                        "binding_id": binding.get("id")
                    }
                else:
                    logger.error(f"Failed to store MAC binding in database for user {user_id}: response.data is empty")
                    return None
                    
            except Exception as db_error:
                logger.error(f"Database error during MAC binding for user {user_id}: {type(db_error).__name__}: {str(db_error)}")
                import traceback
                logger.error(f"Database error traceback: {traceback.format_exc()}")
                return None
                
        except MACSnifferError as e:
            logger.error(f"MAC sniffer error for user {user_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in capture_and_bind_mac for user {user_id}: {str(e)}")
            return None

    @staticmethod
    async def get_active_binding(user_id: str) -> Optional[Dict]:
        """Get the currently active MAC binding for a user"""
        try:
            response = supabase.table("mac_address_bindings").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True).limit(1).execute()
            
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching active binding for user {user_id}: {str(e)}")
            return None

    @staticmethod
    async def verify_mac(user_id: str, ip_address: str = None, user_agent: str = None) -> Dict:
        """
        Verify that the current system MAC matches the stored MAC for the user.
        
        Args:
            user_id: UUID of the user
            ip_address: IP address of the request
            user_agent: User agent of the request
            
        Returns:
            Dict with verification status and details
        """
        logger.info(f"Starting MAC verification for user {user_id}")
        try:
            binding = await MACManager.get_active_binding(user_id)
            logger.info(f"Active binding lookup for user {user_id}: found={bool(binding)}")
            
            if not binding:
                logger.warning(f"No active MAC binding found for user {user_id}")
                await MACManager._log_verification(
                    user_id, None, None, None, False, ip_address, user_agent,
                    "No active binding found"
                )
                return {
                    "verified": False,
                    "reason": "no_binding",
                    "message": "No MAC binding found for user"
                }
            
            logger.info(f"Found binding for user {user_id}: binding_id={binding.get('id')}")
            
            current_mac = MACAddressSniffer.get_system_mac()
            logger.info(f"Current MAC captured for user {user_id}: {current_mac}")
            
            if not current_mac:
                logger.error(f"Failed to capture MAC for verification for user {user_id}")
                await MACManager._log_verification(
                    user_id, binding.get("id"), None, binding["mac_address"], 
                    False, ip_address, user_agent, "Failed to capture current MAC"
                )
                return {
                    "verified": False,
                    "reason": "capture_failed",
                    "message": "Unable to capture system MAC for verification"
                }
            
            secret_key = settings.MAC_VERIFICATION_KEY or "default-secret"
            logger.info(f"Verifying MAC for user {user_id}: current={current_mac}, stored={binding['mac_address']}")
            
            is_valid = MACAddressSniffer.verify_mac(
                current_mac,
                binding["mac_address"],
                binding["mac_checksum"],
                user_id,
                secret_key
            )
            logger.info(f"MAC verification result for user {user_id}: valid={is_valid}")
            
            if is_valid:
                try:
                    logger.info(f"Updating verification count for user {user_id}")
                    supabase.table("mac_address_bindings").update({
                        "last_verified": "now()",
                        "last_seen": "now()",
                        "verification_count": binding.get("verification_count", 0) + 1
                    }).eq("id", binding["id"]).execute()
                    logger.info(f"Verification count updated for user {user_id}")
                except Exception as e:
                    logger.error(f"Error updating verification count for user {user_id}: {str(e)}")
                
                logger.info(f"Logging successful verification for user {user_id}")
                await MACManager._log_verification(
                    user_id, binding.get("id"), current_mac, binding["mac_address"],
                    True, ip_address, user_agent
                )
                
                return {
                    "verified": True,
                    "reason": "success",
                    "message": "MAC verification successful"
                }
            else:
                logger.warning(f"MAC verification failed for user {user_id}: {current_mac} != {binding['mac_address']}")
                try:
                    supabase.table("mac_address_bindings").update({
                        "failed_verification_count": binding.get("failed_verification_count", 0) + 1
                    }).eq("id", binding["id"]).execute()
                except Exception as e:
                    logger.error(f"Error updating failure count: {str(e)}")
                
                logger.info(f"Logging failed verification for user {user_id}")
                await MACManager._log_verification(
                    user_id, binding.get("id"), current_mac, binding["mac_address"],
                    False, ip_address, user_agent, "MAC mismatch"
                )
                
                return {
                    "verified": False,
                    "reason": "mac_mismatch",
                    "message": "Device MAC address does not match recorded binding"
                }
                
        except Exception as e:
            logger.error(f"Error during MAC verification for user {user_id}: {str(e)}")
            return {
                "verified": False,
                "reason": "verification_error",
                "message": "An error occurred during MAC verification"
            }

    @staticmethod
    async def _log_verification(user_id: str, binding_id: str, mac_address: str, 
                               expected_mac: str, success: bool, ip_address: str = None,
                               user_agent: str = None, error_message: str = None):
        """Log MAC verification attempt"""
        try:
            log_entry = {
                "user_id": user_id,
                "binding_id": binding_id,
                "mac_address": mac_address,
                "expected_mac": expected_mac,
                "verification_status": "success" if success else "failed",
                "checksum_match": success,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "error_message": error_message
            }
            logger.debug(f"Logging verification for user {user_id}: {log_entry}")
            response = supabase.table("mac_verification_log").insert(log_entry).execute()
            logger.info(f"Verification logged for user {user_id}: status={'success' if success else 'failed'}")
        except Exception as e:
            logger.error(f"Error logging verification for user {user_id}: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    @staticmethod
    async def get_user_bindings(user_id: str) -> list:
        """Get all MAC bindings for a user"""
        try:
            response = supabase.table("mac_address_bindings").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching bindings for user {user_id}: {str(e)}")
            return []

    @staticmethod
    async def deactivate_binding(binding_id: str) -> bool:
        """Deactivate a MAC binding (force re-authentication)"""
        try:
            response = supabase.table("mac_address_bindings").update({
                "is_active": False
            }).eq("id", binding_id).execute()
            
            logger.info(f"Deactivated MAC binding: {binding_id}")
            return True
        except Exception as e:
            logger.error(f"Error deactivating binding {binding_id}: {str(e)}")
            return False

    @staticmethod
    async def get_verification_log(user_id: str, limit: int = 100) -> list:
        """Get MAC verification log for a user"""
        try:
            response = supabase.table("mac_verification_log").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(limit).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching verification log for user {user_id}: {str(e)}")
            return []
