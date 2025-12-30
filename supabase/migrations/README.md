# Supabase Migrations

This directory contains SQL migrations for the Supabase database setup.

## How to Apply Migrations

### Option 1: Using Supabase CLI
```bash
supabase migration up
```

### Option 2: Manual Application via Supabase Dashboard
1. Go to Supabase Dashboard → SQL Editor
2. Create a new query
3. Copy the entire contents of the migration file
4. Execute the query

## Migrations

### 001_setup_auth_triggers.sql
Sets up the following:
- Creates the `profiles` table if it doesn't exist
- Enables Row Level Security (RLS) on the profiles table
- Creates trigger functions to automatically sync auth.users with profiles table
- Handles email updates automatically
- Creates utility functions for profile management

This migration fixes the following issues:
- **NULL email constraint errors**: Ensures email is always populated from auth.users
- **Missing profile records**: Automatically creates profiles when users sign up
- **Email synchronization**: Updates profile email when auth user email changes

### 002_setup_subscriptions_rls.sql
Sets up the following:
- Creates the `subscription_plans` table for managing subscription tiers
- Creates the `subscriptions` table for user subscription records
- Creates the `payment_requests` table for managing payment submissions
- Creates the `token_transactions` table for tracking token usage
- Enables RLS on all tables to ensure users can only access their own data
- Sets up proper indexes for efficient queries

This migration fixes the following issues:
- **Subscription data access**: Ensures users can only view their own subscriptions
- **Payment request tracking**: Ensures users can only see their payment requests
- **Token transaction history**: Ensures users can only view their token transactions
- **Public plan visibility**: Allows all users to view available subscription plans

## Important Notes

- These migrations use PostgreSQL and are specific to Supabase
- The triggers ensure data consistency between auth.users and the profiles table
- RLS policies ensure users can only access their own data
- Service role key can bypass RLS for backend operations (recommended for backend)
- Always apply migrations in order (001, then 002, etc.)
