#!/usr/bin/env python3
"""
Quick diagnostic script to check environment configuration
Run this locally to verify all required variables are set
"""

import os
from pathlib import Path

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_env():
    print(f"\n{BLUE}═══════════════════════════════════════{RESET}")
    print(f"{BLUE}Environment Configuration Check{RESET}")
    print(f"{BLUE}═══════════════════════════════════════{RESET}\n")
    
    # Load .env
    env_file = Path('.env')
    if not env_file.exists():
        print(f"{RED}✗ .env file not found!{RESET}")
        return False
    
    env_vars = {}
    with open('.env') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    # Required variables
    required = {
        'SUPABASE_URL': 'Supabase Project URL',
        'SUPABASE_SERVICE_KEY': 'Supabase Service Role Key',
        'SUPABASE_ANON_KEY': 'Supabase Anon Key',
        'SUPABASE_JWT_SECRET': 'Supabase JWT Secret',
        'SECRET_KEY': 'FastAPI Secret Key',
        'GOOGLE_API_KEY': 'Google API Key',
        'ENVIRONMENT': 'Environment (development/production)',
    }
    
    # Optional variables
    optional = {
        'DATABASE_URL': 'Database URL (defaults to SQLite)',
        'ADMIN_PASSWORD': 'Admin Password',
    }
    
    # Check required variables
    print(f"{YELLOW}REQUIRED VARIABLES:{RESET}")
    all_ok = True
    for var, description in required.items():
        value = env_vars.get(var, '').strip()
        
        if not value:
            print(f"{RED}  ✗ {var:<25} - {description}{RESET}")
            print(f"    {RED}Missing or empty{RESET}")
            all_ok = False
        elif value.startswith('"') or value.startswith("'"):
            print(f"{YELLOW}  ⚠ {var:<25} - {description}{RESET}")
            print(f"    {YELLOW}Has quotes (remove them!){RESET}")
            all_ok = False
        else:
            # Hide sensitive values
            if 'KEY' in var or 'SECRET' in var or 'PASSWORD' in var:
                display = value[:20] + '...' if len(value) > 20 else value
            else:
                display = value
            print(f"{GREEN}  ✓ {var:<25} - {description}{RESET}")
            print(f"    Value: {display}")
    
    print(f"\n{YELLOW}OPTIONAL VARIABLES:{RESET}")
    for var, description in optional.items():
        value = env_vars.get(var, '').strip()
        if value:
            print(f"{GREEN}  ✓ {var:<25} - {description}{RESET}")
        else:
            print(f"{YELLOW}  - {var:<25} - {description}{RESET}")
            print(f"    Not set (will use default)")
    
    print(f"\n{BLUE}═══════════════════════════════════════{RESET}\n")
    
    if all_ok:
        print(f"{GREEN}✓ All required variables are set!{RESET}")
        print(f"{GREEN}You can deploy to Vercel{RESET}\n")
        return True
    else:
        print(f"{RED}✗ Some variables are missing or incorrectly formatted!{RESET}")
        print(f"{RED}Please fix them before deploying{RESET}\n")
        return False

def check_files():
    """Check if critical files exist"""
    print(f"{YELLOW}CHECKING CRITICAL FILES:{RESET}\n")
    
    files = [
        'app/main.py',
        'app/api/routes/auth.py',
        'app/config.py',
        'app/core/supabase_client.py',
        '.env',
        'requirements.txt',
    ]
    
    all_exist = True
    for file_path in files:
        if Path(file_path).exists():
            print(f"{GREEN}  ✓ {file_path}{RESET}")
        else:
            print(f"{RED}  ✗ {file_path} (MISSING!){RESET}")
            all_exist = False
    
    print()
    return all_exist

def main():
    files_ok = check_files()
    env_ok = check_env()
    
    if files_ok and env_ok:
        print(f"{GREEN}✓ Everything looks good!{RESET}")
        print(f"{GREEN}Next steps:{RESET}")
        print(f"  1. Add env vars to Vercel: Settings → Environment Variables")
        print(f"  2. Redeploy: vercel deploy --prod")
        print(f"  3. Check health: curl https://your-backend.vercel.app/health")
        return 0
    else:
        print(f"{RED}✗ Please fix the issues above{RESET}")
        return 1

if __name__ == '__main__':
    exit(main())
