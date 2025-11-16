# Railway Cron Job Setup Guide

This guide explains how to set up automated daily report generation on Railway.

## Overview

The system automatically generates a 90-day proposal follow-up report every day at midnight UTC using Railway's cron job feature.

## Setup Steps

### 1. Deploy to Railway

If you haven't already, deploy your application to Railway:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link to your project (or create new)
railway link

# Deploy
railway up
```

### 2. Configure Environment Variables

In your Railway dashboard:

1. Go to your project
2. Click on your service
3. Navigate to "Variables" tab
4. Add the following variable:

```
ADMIN_EMAIL=admin@prezlab.com
```

This email determines which user account will own the automated reports.

### 3. Enable Cron Jobs

Railway automatically detects the `railway.json` file and sets up cron jobs. The configuration is:

```json
{
  "crons": [
    {
      "name": "daily-90day-report",
      "schedule": "0 0 * * *",
      "command": "python scripts/daily_report_cron.py"
    }
  ]
}
```

**Schedule Format**: `0 0 * * *` (Cron syntax)
- Minute: 0
- Hour: 0 (midnight)
- Day of month: * (every day)
- Month: * (every month)
- Day of week: * (every day of week)

This means the job runs **every day at 00:00 UTC**.

### 4. Verify Deployment

After deployment:

1. Check Railway logs for confirmation that cron is scheduled
2. Wait for the first execution (or trigger manually - see below)
3. Monitor logs for execution status

## Monitoring

### View Cron Execution Logs

In Railway dashboard:
1. Go to your service
2. Click "Deployments"
3. Select the active deployment
4. View logs

Filter logs by searching for: `daily-90day-report` or `Automated 90-Day Report`

### Success Indicators

Look for these log messages:

```
✅ Successfully generated and saved report: Automated 90-Day Report - 2025-11-16
   - Total threads: 150
   - Needs followup: 45
   - Engaged: 105
```

### Error Detection

If the job fails, you'll see:
```
❌ Error generating daily report: [error message]
```

## Manual Testing

### Local Testing

Before deploying, test the cron script locally:

```bash
# Make sure your .env file has all required variables
python scripts/daily_report_cron.py
```

### Manual Trigger on Railway

You can manually trigger the cron job via Railway CLI:

```bash
railway run python scripts/daily_report_cron.py
```

## Customization

### Change Schedule

To run at a different time, edit `railway.json`:

```json
{
  "crons": [
    {
      "name": "daily-90day-report",
      "schedule": "0 9 * * *",  // 9 AM UTC daily
      "command": "python scripts/daily_report_cron.py"
    }
  ]
}
```

Common schedules:
- `0 0 * * *` - Daily at midnight UTC
- `0 9 * * *` - Daily at 9 AM UTC
- `0 0 * * 1` - Every Monday at midnight UTC
- `0 */6 * * *` - Every 6 hours
- `0 0 1 * *` - First day of every month at midnight UTC

### Change Report Parameters

Edit `scripts/daily_report_cron.py` to modify report settings:

```python
report_config = {
    'report_type': '90day',      # or '30day', '60day'
    'days_back': 90,              # lookback period
    'no_response_days': 3,        # threshold for "needs followup"
    'engage_email': admin_email   # user email
}
```

### Add Multiple Cron Jobs

Add more jobs to `railway.json`:

```json
{
  "crons": [
    {
      "name": "daily-90day-report",
      "schedule": "0 0 * * *",
      "command": "python scripts/daily_report_cron.py"
    },
    {
      "name": "weekly-summary",
      "schedule": "0 9 * * 1",
      "command": "python scripts/weekly_summary_cron.py"
    }
  ]
}
```

## Accessing Generated Reports

Automated reports appear in the web interface:

1. Navigate to "Proposal Follow-ups" page
2. Click "Saved Reports" tab
3. Look for reports named: `Automated 90-Day Report - YYYY-MM-DD`

All users can view these reports. They're stored in the Supabase `analysis_cache` table.

## Troubleshooting

### Cron Job Not Running

1. **Check railway.json is committed**: The file must be in your repository root
2. **Verify environment variables**: Ensure `ADMIN_EMAIL` and all required variables are set
3. **Check Railway logs**: Look for cron scheduling confirmation on deployment
4. **Rebuild**: Sometimes a fresh deployment helps: `railway up --detach`

### Script Fails to Find Admin User

Error: `Admin user not found: admin@prezlab.com`

**Solution**:
1. Check the email in `ADMIN_EMAIL` matches an actual user in Supabase `users` table
2. Or create the admin user via the web interface first

### Database Connection Issues

Error: `Error connecting to Supabase`

**Solution**:
1. Verify `SUPABASE_URL` and `SUPABASE_KEY` are set in Railway environment variables
2. Check Supabase service is running and accessible
3. Verify network access between Railway and Supabase

### Reports Not Appearing in UI

If the script succeeds but reports don't show:

1. Check the frontend is fetching from the correct API endpoint
2. Verify cache settings in `ProposalFollowupsPage.tsx` (staleTime should be 10 seconds)
3. Refresh the page or switch tabs to trigger refetch
4. Check Supabase `analysis_cache` table directly to verify data was saved

## Security Considerations

- The cron job runs with the credentials of the `ADMIN_EMAIL` user
- Ensure this user has appropriate permissions in Odoo and Supabase
- Rotate API keys regularly
- Monitor logs for unauthorized access patterns

## Cost Implications

Railway cron jobs:
- Run on your existing service (no extra charge)
- Consume resources during execution
- LLM API calls (OpenAI GPT-5) incur per-token charges

Monitor your OpenAI usage dashboard to track costs from automated reports.

## Support

For issues or questions:
- Check Railway documentation: https://docs.railway.app/guides/cron-jobs
- Review application logs in Railway dashboard
- Test locally first with `python scripts/daily_report_cron.py`
