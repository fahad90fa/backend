from app.config import get_settings
from app.core.mock_supabase import MockSupabaseClient
import logging
import sys

logger = logging.getLogger(__name__)
settings = get_settings()

supabase = None

try:
    try:
        from supabase import create_client
    except ImportError:
        logger.warning("Supabase library not installed, will use mock client")
        raise ImportError("supabase library not available")
    
    if not settings.SUPABASE_URL:
        raise ValueError("SUPABASE_URL is not configured")
    if not settings.SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_SERVICE_KEY is not configured")
    if not settings.SUPABASE_JWT_SECRET:
        logger.warning("SUPABASE_JWT_SECRET is not configured - token verification may fail")
    
    logger.info(f"Initializing Supabase client with URL: {settings.SUPABASE_URL}")
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    logger.info("Supabase client initialized successfully")
    
except Exception as e:
    error_msg = f"Failed to initialize Supabase client: {str(e)}"
    logger.error(error_msg)
    
    if settings.ENVIRONMENT == "production":
        print(f"WARNING: {error_msg}", file=sys.stderr)
        print(
            "Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set in Vercel environment",
            file=sys.stderr
        )
        if isinstance(e, ValueError):
            raise
    
    if supabase is None:
        if settings.ENVIRONMENT == "development":
            logger.warning("Using Mock Supabase Client for development")
            supabase = MockSupabaseClient()
        else:
            logger.error("Cannot initialize Supabase in production - will raise on auth attempts")
            raise e
