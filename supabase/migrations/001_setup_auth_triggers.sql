-- Supabase Auth Trigger Setup
-- This migration creates triggers to sync Supabase Auth users with the profiles table

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the profiles table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    full_name VARCHAR(255),
    avatar_url TEXT,
    subscription_tier VARCHAR(50) DEFAULT 'free',
    subscription_status VARCHAR(50) DEFAULT 'active',
    tokens_total INTEGER DEFAULT 20,
    tokens_used INTEGER DEFAULT 0,
    bonus_tokens INTEGER DEFAULT 0,
    chat_security_enabled BOOLEAN DEFAULT FALSE,
    chat_password_set_at TIMESTAMP WITH TIME ZONE,
    chat_security_hint TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_username ON public.profiles(username);

-- Enable RLS on profiles table
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;

-- Create policies for profiles table
CREATE POLICY "Users can view their own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Create trigger function to handle new user creation
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, username, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'username', SPLIT_PART(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data->>'full_name', SPLIT_PART(NEW.email, '@', 1))
    )
    ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing triggers before recreating
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS on_auth_user_email_changed ON auth.users;

-- Create trigger for new user
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Create trigger function for email updates
CREATE OR REPLACE FUNCTION public.handle_user_email_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.email IS DISTINCT FROM NEW.email THEN
        UPDATE public.profiles
        SET email = NEW.email, updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger for email updates
CREATE TRIGGER on_auth_user_email_changed
    AFTER UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_user_email_update();

-- Create function to ensure profile exists (utility function)
CREATE OR REPLACE FUNCTION public.ensure_profile_exists(user_id UUID, user_email VARCHAR)
RETURNS VOID AS $$
BEGIN
    INSERT INTO public.profiles (id, email, username)
    VALUES (user_id, user_email, SPLIT_PART(user_email, '@', 1))
    ON CONFLICT (id) DO NOTHING;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant appropriate permissions
GRANT EXECUTE ON FUNCTION public.handle_new_user TO postgres, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.handle_user_email_update TO postgres, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.ensure_profile_exists TO postgres, anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON public.profiles TO anon, authenticated, service_role;
