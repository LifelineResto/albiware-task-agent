# Enhanced AI Agent System v2.0 - Deployment Guide

## 🚀 What's New

### Critical Bug Fix
- **Fixed:** `'str' object has no attribute 'get'` error in Albiware API responses
- Both `get_all_projects()` and `get_all_tasks()` now properly extract the `data` array from API responses

### New Features
1. **Contact Tracking** - Monitors new contacts added to Albiware
2. **24-Hour Follow-up SMS** - Automatically sends follow-up texts to technicians 24 hours after contact creation
3. **Two-Way SMS Conversations** - Handles interactive SMS conversations with outcome tracking
4. **Automated Project Creation** - Uses browser automation to create projects in Albiware when "appointment set"
5. **Enhanced Analytics** - Tracks contacts, conversations, and project creation success rates

---

## 📋 Deployment Steps

### Step 1: Railway Environment Variables

The code has been pushed to GitHub. Railway will automatically detect and redeploy.

**Set these environment variables in Railway:**

```bash
# Albiware Configuration
ALBIWARE_API_KEY=your_albiware_api_key_here
ALBIWARE_BASE_URL=https://api.albiware.com/v5
ALBIWARE_EMAIL=your_albiware_email@example.com
ALBIWARE_PASSWORD=your_albiware_password

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=+1234567890

# Phone Numbers
STAFF_PHONE_NUMBERS=+1234567890
TECHNICIAN_PHONE_NUMBER=+1234567890

# Configuration
POLLING_INTERVAL_MINUTES=15
REMINDER_HOURS_BEFORE_DUE=24
MAX_REMINDERS_PER_TASK=5
PORT=8080
```

**Note:** Actual credentials are stored in the `#LifelineRestorationCredentials.txt` file in the project folder.

**Note:** `DATABASE_URL` should be automatically set by Railway's PostgreSQL plugin.

---

### Step 2: Install Playwright Browsers

After the deployment completes, run this command in Railway's terminal:

```bash
playwright install chromium
```

This installs the Chromium browser needed for automated project creation.

---

### Step 3: Configure Twilio Webhook

For two-way SMS conversations to work, configure Twilio to send incoming SMS to your Railway app:

1. Go to **Twilio Console** → Phone Numbers → Manage → Active Numbers
2. Click on your Twilio number: **+18555660689**
3. Scroll to **Messaging Configuration**
4. Under **A MESSAGE COMES IN**, set:
   - **Webhook**: `https://your-railway-app.railway.app/webhooks/twilio/sms`
   - **HTTP Method**: `POST`
5. Click **Save**

**Get your Railway URL:**
```bash
railway domain
```

---

## 🔄 How It Works

### Task Tracking (Existing)
- Syncs tasks from Albiware every 15 minutes
- Sends SMS reminders to staff before due dates
- Tracks completion and analytics

### Contact Tracking (NEW)
1. **Every 10 minutes:** Syncs contacts from Albiware
2. **New contact detected:** Schedules 24-hour follow-up SMS
3. **24 hours later:** Sends SMS to technician: "Hi Rudy, were you able to make contact with [Contact Name] yet? Reply YES or NO."

### SMS Conversation Flow (NEW)
1. **Technician replies YES:**
   - AI asks: "What was the outcome? Reply with: 1 - Appointment set, 2 - Looking for quotes, 3 - Waste of time, 4 - Something else"
   
2. **Technician replies with outcome:**
   - If **"Appointment set"** → Triggers automated project creation
   - Otherwise → Logs outcome and completes conversation

3. **Technician replies NO:**
   - Logs "no contact made" and ends conversation

### Automated Project Creation (NEW)
- **Every 5 minutes:** Checks for contacts with "appointment set" outcome
- Uses browser automation to:
  1. Log into Albiware
  2. Navigate to project creation
  3. Fill form with contact details
  4. Submit and verify creation
- Sends confirmation SMS to technician when complete

---

## 📊 API Endpoints

### New Endpoints

**Get Contacts:**
```
GET /api/contacts?status=new&limit=100
```

**Get Conversations:**
```
GET /api/conversations?contact_id=123&limit=100
```

**Enhanced Analytics:**
```
GET /api/analytics/summary
```
Returns:
```json
{
  "tasks": {
    "total": 45,
    "completed": 32,
    "active": 13
  },
  "contacts": {
    "total": 28,
    "follow_ups_sent": 25,
    "appointments_set": 8,
    "projects_created": 7
  },
  "conversations": {
    "total": 25,
    "completed": 22,
    "active": 3
  }
}
```

---

## 🧪 Testing

### Test Contact Follow-up
1. Add a new contact in Albiware
2. Wait for sync (or trigger manually via API)
3. Check that follow-up is scheduled for 24 hours later
4. For testing, you can manually update the `follow_up_scheduled_at` in database to trigger immediately

### Test SMS Conversation
1. Send SMS to your Twilio number from the technician's phone
2. Check logs to see conversation handling
3. Verify responses are sent correctly

### Test Project Creation
1. Set a contact's outcome to "appointment_set" in database
2. Wait for project creation scheduler (5 minutes)
3. Check Albiware for new project
4. Review logs for any errors

---

## 🐛 Troubleshooting

### Issue: SMS not being received
- Check Twilio webhook is configured correctly
- Verify Railway URL is accessible
- Check Railway logs for webhook errors

### Issue: Project creation failing
- Ensure Playwright browsers are installed: `playwright install chromium`
- Check Albiware login credentials are correct
- Review screenshot in `/tmp/` directory for browser automation errors

### Issue: Database errors
- Ensure PostgreSQL plugin is attached in Railway
- Check `DATABASE_URL` environment variable is set
- Run migrations if needed

---

## 📈 Monitoring

**Check Application Health:**
```
GET /health
```

**View Logs in Railway:**
```bash
railway logs
```

**Database Access:**
```bash
railway connect postgres
```

---

## 🔐 Security Notes

- All credentials are stored as environment variables
- GitHub token is embedded in git remote URL (local only)
- Twilio validates webhook requests
- Database credentials managed by Railway

---

## 📞 Support

For issues or questions:
- Check Railway logs first
- Review this deployment guide
- Test individual components (SMS, API, browser automation)

---

## 🎯 Next Steps

1. ✅ Push code to GitHub (DONE)
2. ⏳ Set Railway environment variables
3. ⏳ Install Playwright browsers
4. ⏳ Configure Twilio webhook
5. ⏳ Test the system end-to-end
6. ⏳ Monitor for 24 hours to ensure stability
