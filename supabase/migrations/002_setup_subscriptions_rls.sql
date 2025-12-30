-- Supabase Subscriptions and Payments RLS Setup
-- This migration creates tables and RLS policies for subscriptions, payments, and tokens

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create subscription_plans table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.subscription_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    monthly_price INTEGER NOT NULL,
    yearly_price INTEGER NOT NULL,
    tokens_total INTEGER NOT NULL,
    tokens_monthly_limit INTEGER,
    features JSONB DEFAULT '[]'::jsonb,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create subscriptions table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES public.subscription_plans(id),
    plan_name VARCHAR(255) NOT NULL,
    billing_cycle VARCHAR(20) NOT NULL,
    price_paid INTEGER NOT NULL,
    tokens_total INTEGER NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancel_reason TEXT,
    activated_by_admin BOOLEAN DEFAULT FALSE,
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create payment_requests table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.payment_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES public.subscription_plans(id),
    plan_name VARCHAR(255) NOT NULL,
    billing_cycle VARCHAR(20) NOT NULL,
    amount INTEGER NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'pending',
    transaction_reference VARCHAR(255),
    payment_date TIMESTAMP WITH TIME ZONE,
    payment_screenshot_url TEXT,
    rejection_reason TEXT,
    admin_confirmed_at TIMESTAMP WITH TIME ZONE,
    admin_notes TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create token_transactions table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.token_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    balance_before INTEGER DEFAULT 0,
    balance_after INTEGER DEFAULT 0,
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON public.subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON public.subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_payment_requests_user_id ON public.payment_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_requests_status ON public.payment_requests(status);
CREATE INDEX IF NOT EXISTS idx_token_transactions_user_id ON public.token_transactions(user_id);

-- Enable RLS on subscription_plans table
ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Plans are publicly readable" ON public.subscription_plans;

-- Create policies for subscription_plans table (publicly readable)
CREATE POLICY "Plans are publicly readable" ON public.subscription_plans
    FOR SELECT USING (TRUE);

-- Enable RLS on subscriptions table
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own subscriptions" ON public.subscriptions;
DROP POLICY IF EXISTS "Users can read their subscription history" ON public.subscriptions;

-- Create policies for subscriptions table
CREATE POLICY "Users can view their own subscriptions" ON public.subscriptions
    FOR SELECT USING (auth.uid() = user_id);

-- Enable RLS on payment_requests table
ALTER TABLE public.payment_requests ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own payment requests" ON public.payment_requests;

-- Create policies for payment_requests table
CREATE POLICY "Users can view their own payment requests" ON public.payment_requests
    FOR SELECT USING (auth.uid() = user_id);

-- Enable RLS on token_transactions table
ALTER TABLE public.token_transactions ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own token transactions" ON public.token_transactions;

-- Create policies for token_transactions table
CREATE POLICY "Users can view their own token transactions" ON public.token_transactions
    FOR SELECT USING (auth.uid() = user_id);

-- Grant appropriate permissions
GRANT SELECT ON public.subscription_plans TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON public.subscriptions TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON public.payment_requests TO authenticated, service_role;
GRANT SELECT, INSERT ON public.token_transactions TO authenticated, service_role;

-- Grant permissions to service_role for admin operations
GRANT ALL PRIVILEGES ON public.subscriptions TO service_role;
GRANT ALL PRIVILEGES ON public.payment_requests TO service_role;
GRANT ALL PRIVILEGES ON public.token_transactions TO service_role;
GRANT ALL PRIVILEGES ON public.subscription_plans TO service_role;
