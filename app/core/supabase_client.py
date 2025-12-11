from supabase import create_client
from app.config import get_settings
from app.core.mock_supabase import MockSupabaseClient

settings = get_settings()

try:
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
except Exception as e:
    print(f"Warning: Failed to initialize Supabase: {e}")
    supabase = MockSupabaseClient()
