# Email Integration Setup Guide

## Overview

This system integrates with Microsoft Outlook/Office 365 to search emails related to lost leads. Each user can authorize their own email account, and the system securely stores OAuth2 tokens locally.

## Architecture

- **OAuth2 Flow**: Users authorize via Microsoft Azure AD
- **Token Storage**: Tokens stored locally in `.email_tokens/` directory (gitignored)
- **Multi-User Support**: Each user's tokens stored separately
- **Auto-Refresh**: Access tokens automatically refreshed when expired

---

## Setup Steps

### 1. Create Azure App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App Registrations**
3. Click **+ New registration**

**Configure the app:**
- **Name**: Lead Automation Email Access
- **Supported account types**: Accounts in any organizational directory (Multitenant)
- **Redirect URI**:
  - Platform: `Web`
  - URI: `http://localhost:8000/auth/outlook/callback`

4. Click **Register**

### 2. Get Client Credentials

After registration:

1. Copy the **Application (client) ID** - this is your `MICROSOFT_CLIENT_ID`
2. Go to **Certificates & secrets** → **+ New client secret**
3. Add description (e.g., "Lead Automation")
4. Set expiration (recommend 24 months)
5. Copy the **Value** (not ID) - this is your `MICROSOFT_CLIENT_SECRET`
   - ⚠️ **Important**: Save this now! You can't view it again.

### 3. Configure API Permissions

1. Go to **API permissions** → **+ Add a permission**
2. Select **Microsoft Graph** → **Delegated permissions**
3. Add these permissions:
   - ✅ `Mail.Read` - Read user mail
   - ✅ `User.Read` - Sign in and read user profile
   - ✅ `offline_access` - Maintain access to data (for refresh tokens)

4. Click **Add permissions**
5. (Optional) Click **Grant admin consent** if you're an admin

### 4. Update Environment Variables

Add these to your `.env` file:

```bash
# Microsoft Outlook/Email OAuth2
MICROSOFT_CLIENT_ID=your-application-id-here
MICROSOFT_CLIENT_SECRET=your-secret-value-here
MICROSOFT_REDIRECT_URI=http://localhost:8000/auth/outlook/callback

# Email search settings
EMAIL_SEARCH_DAYS_BACK=180
EMAIL_SEARCH_LIMIT_PER_LEAD=10
```

### 5. For Production Deployment

When deploying to production:

1. Add production redirect URI to Azure app:
   - Go to **Authentication** → **+ Add a platform** → **Web**
   - Add: `https://your-domain.com/auth/outlook/callback`

2. Update `.env` with production URI:
   ```bash
   MICROSOFT_REDIRECT_URI=https://your-domain.com/auth/outlook/callback
   ```

---

## User Authorization Flow

### For Each User:

1. **Start Authorization**
   - User clicks "Connect Email" in the frontend
   - Frontend calls `/auth/outlook/start`
   - User redirected to Microsoft login page

2. **Microsoft Authorization**
   - User logs in with their Microsoft/Outlook account
   - User grants permissions (Mail.Read, User.Read)
   - Microsoft redirects back to callback URL with authorization code

3. **Token Exchange**
   - Backend exchanges code for access/refresh tokens
   - Stores tokens in `.email_tokens/{user_identifier}.json`
   - Returns success to frontend

4. **Using Email Search**
   - System automatically uses stored tokens
   - Tokens refreshed automatically when expired
   - User can revoke access anytime

---

## API Endpoints

### Start OAuth Flow
```http
GET /auth/outlook/start
```

**Response:**
```json
{
  "authorization_url": "https://login.microsoftonline.com/...",
  "state": "csrf_token"
}
```

### OAuth Callback
```http
POST /auth/outlook/callback
Content-Type: application/json

{
  "code": "authorization_code_from_microsoft",
  "state": "csrf_token",
  "user_identifier": "user@example.com"  // optional
}
```

### Check Authorization Status
```http
GET /auth/outlook/status/{user_identifier}
```

**Response:**
```json
{
  "authorized": true,
  "user_email": "user@example.com",
  "user_name": "John Doe",
  "expires_soon": false
}
```

### Revoke Authorization
```http
DELETE /auth/outlook/{user_identifier}
```

### List Authorized Users (Admin)
```http
GET /auth/outlook/users
```

---

## Email Search API

The Outlook client provides methods to search emails:

```python
from modules.outlook_client import OutlookClient
from modules.email_token_store import EmailTokenStore

# Initialize
outlook = OutlookClient()
token_store = EmailTokenStore()

# Get user's tokens
tokens = token_store.get_tokens("user@example.com")
access_token = tokens["access_token"]

# Search emails
emails = outlook.search_emails(
    access_token=access_token,
    query="Chalhoub Group",
    limit=25,
    days_back=180
)

# Search emails for a specific lead
emails = outlook.search_emails_for_lead(
    access_token=access_token,
    lead_data={
        "partner_name": "Chalhoub Group",
        "contact_name": "Karen Nassar",
        "email_from": "karen.nassar@chalhoub.com"
    },
    limit=10,
    days_back=180
)
```

---

## Security Notes

### Token Storage
- Tokens stored in `.email_tokens/` directory
- Directory is gitignored to prevent accidental commits
- Files named by sanitized user identifier
- Each file contains: access_token, refresh_token, expiry, user info

### Token Security Best Practices
1. ✅ Never commit `.email_tokens/` directory
2. ✅ Never commit `.env` with real credentials
3. ✅ Use environment variables for client secrets
4. ✅ Rotate client secrets periodically
5. ✅ Monitor Azure app for unusual activity

### Refresh Token Handling
- Refresh tokens have no expiration (until revoked)
- Access tokens expire in ~1 hour
- System automatically refreshes access tokens when needed
- Users can revoke access anytime via UI or API

---

## Troubleshooting

### "Invalid redirect URI"
- Ensure redirect URI in code matches Azure app configuration exactly
- Check for trailing slashes, http vs https
- Verify port numbers match

### "Insufficient privileges"
- Ensure `Mail.Read`, `User.Read`, `offline_access` permissions added
- Try granting admin consent in Azure portal

### "Token expired" errors
- System should auto-refresh tokens
- If persistent, user may need to re-authorize
- Check refresh token is being stored correctly

### "MICROSOFT_CLIENT_ID not set"
- Verify `.env` file exists and has correct values
- Restart backend server after updating `.env`

---

## Next Steps

1. **Frontend UI**: Create React component for authorization flow
2. **Lost Lead Integration**: Integrate email search into lost lead analysis
3. **Email Display**: Show relevant emails in Lost Leads page
4. **Admin Dashboard**: Monitor authorized users

---

## Example Frontend Flow

```typescript
// Start authorization
const startAuth = async () => {
  const response = await api.get('/auth/outlook/start');
  const { authorization_url } = response.data;

  // Open Microsoft login in new window or redirect
  window.location.href = authorization_url;
};

// Check if user is authorized
const checkAuth = async (userEmail: string) => {
  const response = await api.get(`/auth/outlook/status/${userEmail}`);
  return response.data.authorized;
};

// Revoke authorization
const revokeAuth = async (userEmail: string) => {
  await api.delete(`/auth/outlook/${userEmail}`);
};
```

---

## Production Checklist

- [ ] Azure app created with production redirect URI
- [ ] Environment variables configured
- [ ] `.email_tokens/` in `.gitignore`
- [ ] HTTPS enabled on production domain
- [ ] Token refresh logic tested
- [ ] Error handling implemented
- [ ] User revocation flow tested
- [ ] Admin monitoring dashboard created
