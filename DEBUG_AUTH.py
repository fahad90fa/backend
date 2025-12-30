#!/usr/bin/env python3

import os
import sys
from datetime import datetime
import json

try:
    from jose import jwt
except ImportError:
    print("ERROR: python-jose not installed. Run: pip install python-jose[cryptography]")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))

from app.config import get_settings

def check_configuration():
    print("\n" + "="*60)
    print("CyberScholar AI - Auth Configuration Checker")
    print("="*60 + "\n")
    
    try:
        settings = get_settings()
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        return False
    
    print("✓ Configuration loaded successfully\n")
    
    print("Key Configuration Values:")
    print("-" * 60)
    print(f"SUPABASE_URL: {settings.SUPABASE_URL}")
    print(f"SUPABASE_JWT_SECRET: {settings.SUPABASE_JWT_SECRET[:20]}...")
    print(f"SUPABASE_SERVICE_KEY: {settings.SUPABASE_SERVICE_KEY[:20]}...")
    print(f"SECRET_KEY: {settings.SECRET_KEY[:20]}...")
    print(f"ALGORITHM: {settings.ALGORITHM}")
    print(f"ENVIRONMENT: {settings.ENVIRONMENT}\n")
    
    if not settings.SUPABASE_JWT_SECRET:
        print("⚠️  WARNING: SUPABASE_JWT_SECRET is not set!")
        print("   This will cause token verification to fail.")
        print("   Get it from: Supabase Dashboard → Settings → API → JWT Secret\n")
        return False
    
    if settings.SECRET_KEY == settings.SUPABASE_JWT_SECRET:
        print("⚠️  WARNING: SECRET_KEY and SUPABASE_JWT_SECRET are the same!")
        print("   This might be incorrect. Verify with your Supabase project.")
        print("   SUPABASE_JWT_SECRET should come from Supabase Dashboard.\n")
    
    return True


def test_token_decoding():
    print("\n" + "="*60)
    print("Token Decoding Test")
    print("="*60 + "\n")
    
    settings = get_settings()
    
    test_payload = {"sub": "test-user-id", "email": "test@example.com"}
    
    print("Creating test token with SECRET_KEY...")
    token = jwt.encode(test_payload, settings.SECRET_KEY, algorithm="HS256")
    print(f"Token: {token[:50]}...\n")
    
    print("Attempting to decode with SUPABASE_JWT_SECRET...")
    try:
        decoded = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"])
        print(f"✓ Successfully decoded: {decoded}\n")
    except jwt.InvalidSignatureError:
        print("❌ InvalidSignatureError - Keys don't match!\n")
    except Exception as e:
        print(f"❌ Error: {str(e)}\n")
    
    print("Attempting to decode with SECRET_KEY...")
    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        print(f"✓ Successfully decoded: {decoded}\n")
    except Exception as e:
        print(f"❌ Error: {str(e)}\n")


def show_token_info(token):
    print("\n" + "="*60)
    print("Token Information")
    print("="*60 + "\n")
    
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        print("Token payload (unverified):")
        print(json.dumps(decoded, indent=2))
        print()
        
        if "exp" in decoded:
            exp_time = datetime.fromtimestamp(decoded["exp"])
            now = datetime.now()
            if exp_time < now:
                print(f"❌ Token is EXPIRED (expired at {exp_time})")
            else:
                print(f"✓ Token is valid until {exp_time}")
        
        if "sub" in decoded:
            print(f"✓ User ID: {decoded['sub']}")
        
        if "email" in decoded:
            print(f"✓ Email: {decoded['email']}")
    except Exception as e:
        print(f"❌ Error parsing token: {str(e)}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--token":
        if len(sys.argv) < 3:
            print("Usage: python DEBUG_AUTH.py --token <your_token>")
            sys.exit(1)
        show_token_info(sys.argv[2])
    else:
        check_configuration()
        test_token_decoding()
        
        print("="*60)
        print("To debug a specific token:")
        print(f"  python DEBUG_AUTH.py --token <your_token>")
        print("="*60)


if __name__ == "__main__":
    main()
