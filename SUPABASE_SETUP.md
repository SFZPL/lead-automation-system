# Supabase Setup Guide

## Step 1: Create Supabase Project

1. Go to [https://supabase.com](https://supabase.com)
2. Sign up or log in
3. Click **"New Project"**
4. Fill in:
   - **Organization**: Create one if you don't have it
   - **Project Name**: `prezlab-leads` (or any name)
   - **Database Password**: Generate and **save this password securely**
   - **Region**: Choose closest to your location
   - **Pricing Plan**: Free tier is fine for development
5. Click **"Create new project"**
6. Wait ~2 minutes for provisioning

## Step 2: Get API Credentials

Once the project is created:

1. Go to **Project Settings** (gear icon in sidebar)
2. Click **API** in the left menu
3. Copy these values:
   - **Project URL** (looks like: `https://xxxxx.supabase.co`)
   - **anon public** key (for frontend - starts with `eyJhbGc...`)
   - **service_role** key (for backend - starts with `eyJhbGc...`)

## Step 3: Add Credentials to `.env`

Add these lines to your `.env` file in the project root:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Replace the values with your actual credentials from Step 2.

## Step 4: Run Database Migration

1. In Supabase dashboard, click **SQL Editor** in the left sidebar
2. Click **"New Query"**
3. Copy the entire contents of `supabase_migrations/001_initial_schema.sql`
4. Paste into the SQL editor
5. Click **"Run"** (or press Ctrl+Enter)
6. You should see "Success. No rows returned"

## Step 5: Verify Tables Created

1. Click **Table Editor** in the left sidebar
2. You should see these tables:
   - `analysis_cache`
   - `analysis_schedules`
   - `lead_assignments`
   - `user_preferences`

## Step 6: Install Python Supabase Library

```bash
pip install supabase
```

Or add to `requirements.txt`:
```
supabase==2.3.4
```

## Step 7: Test Connection

Restart your backend server:
```bash
cd api
python run_api.py
```

Look for this log message:
```
✅ Supabase client initialized successfully
```

If you see a warning instead, check your `.env` credentials.

## What This Enables

✅ **90-day analysis caching** - Run once, cached for 3 months
✅ **Weekly analysis caching** - Run Sunday, accessible all week
✅ **Per-user isolation** - Each user has separate cached analyses
✅ **Tab persistence** - State restored on tab switch
✅ **Lead forwarding** - Assign leads to teammates
✅ **User preferences** - Save default settings per user

## Troubleshooting

### Error: "Supabase credentials not found"
- Make sure `.env` file has the three SUPABASE_* variables
- Check that `.env` is in the project root directory
- Restart the backend server after adding credentials

### Error: "Failed to initialize Supabase client"
- Verify the SUPABASE_URL is correct (should start with https://)
- Verify the SUPABASE_SERVICE_ROLE_KEY is the correct key (not anon key)
- Check your internet connection

### Tables not showing in Supabase
- Make sure you ran the migration SQL in the SQL Editor
- Check for SQL errors in the output
- Try running each CREATE TABLE statement separately

## Security Notes

⚠️ **IMPORTANT**:
- Never commit `.env` file to Git
- The `service_role` key bypasses RLS - keep it secret
- Use `anon` key for frontend (coming in next phase)
- RLS policies ensure users only see their own data

## Next Steps

Once Supabase is set up, we'll:
1. Integrate caching into the proposal followups analysis
2. Add lead assignment endpoints to the API
3. Update frontend to use cached data
4. Add collaboration features
