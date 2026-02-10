# Albiware Task Agent

An AI-powered agent system that tracks live project data from Albiware, sends automated SMS reminders for task completion, and maintains comprehensive tracking logs for performance analysis.

## Features

- **Live Data Tracking**: Automatically polls Albiware API for project and task updates
- **Smart Notifications**: Sends SMS reminders based on task due dates and completion status
- **Tracking Analytics**: Maintains detailed logs of all notifications and task completions
- **REST API**: Provides endpoints for monitoring and manual control
- **Railway Integration**: Designed for seamless deployment on Railway platform

## Architecture

The system consists of several microservices:

1. **Albiware Polling Service**: Retrieves project and task data from Albiware API
2. **Notification Engine**: Determines when to send reminders based on configurable rules
3. **Twilio SMS Service**: Sends SMS notifications via Twilio API
4. **Tracking Database**: PostgreSQL database for storing logs and analytics
5. **REST API**: FastAPI application for monitoring and control

## Prerequisites

- Python 3.11+
- PostgreSQL database
- Albiware account with API access
- Twilio account with SMS capabilities
- Railway account (for deployment)

## Installation

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd albiware-task-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file from template:
```bash
cp .env.example .env
```

4. Configure environment variables in `.env`:
   - Add your Albiware API key
   - Add your Twilio credentials
   - Configure database URL
   - Add staff phone numbers

5. Run the application:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### Railway Deployment

1. Install Railway CLI:
```bash
npm install -g @railway/cli
```

2. Login to Railway:
```bash
railway login
```

3. Create a new Railway project:
```bash
railway init
```

4. Add PostgreSQL database:
```bash
railway add --plugin postgresql
```

5. Set environment variables in Railway dashboard or via CLI:
```bash
railway variables set ALBIWARE_API_KEY=your_key_here
railway variables set TWILIO_ACCOUNT_SID=your_sid_here
railway variables set TWILIO_AUTH_TOKEN=your_token_here
railway variables set TWILIO_FROM_NUMBER=+1234567890
railway variables set STAFF_PHONE_NUMBERS=+17024219571,+17025551234
```

6. Deploy to Railway:
```bash
railway up
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ALBIWARE_API_KEY` | Albiware API key | Yes |
| `ALBIWARE_BASE_URL` | Albiware API base URL | No (default provided) |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | Yes |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | Yes |
| `TWILIO_FROM_NUMBER` | Twilio phone number (E.164 format) | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `POLLING_INTERVAL_MINUTES` | Minutes between Albiware polls | No (default: 15) |
| `REMINDER_HOURS_BEFORE_DUE` | Hours before due date to send first reminder | No (default: 24) |
| `MAX_REMINDERS_PER_TASK` | Maximum reminders per task | No (default: 5) |
| `STAFF_PHONE_NUMBERS` | Comma-separated phone numbers | Yes |
| `PORT` | Application port | No (default: 8000) |

### Notification Rules

The system follows these rules for sending notifications:

1. **First Reminder**: Sent 24 hours (configurable) before task due date
2. **Overdue Reminders**: Sent every 24 hours for overdue tasks
3. **Maximum Reminders**: Up to 5 reminders (configurable) per task
4. **SMS Format**: Date/time formatted as MM/DD/YYYY 12hr a.m./p.m.

## API Endpoints

### Health Check
```
GET /health
```
Returns system health status.

### Get Tasks
```
GET /api/tasks?status=incomplete&limit=100
```
Retrieve tasks from the database.

### Get Notifications
```
GET /api/notifications?task_id=123&limit=100
```
Retrieve notification history.

### Get Completion Logs
```
GET /api/completion-logs?limit=100
```
Retrieve task completion logs for analytics.

### Analytics Summary
```
GET /api/analytics/summary
```
Get summary analytics including total tasks, completion rates, and notification metrics.

### Manual Sync
```
POST /api/sync
```
Manually trigger a sync from Albiware.

### Manual Notification Send
```
POST /api/notifications/send
```
Manually trigger notification processing.

## Database Schema

### Tables

1. **tasks**: Stores task information from Albiware
2. **notifications**: Logs all sent notifications
3. **task_completion_logs**: Tracks task completion metrics
4. **system_logs**: Records system events and errors

## Monitoring

The system provides several ways to monitor its operation:

1. **API Endpoints**: Use the REST API to query system status
2. **Database Logs**: Query the database directly for detailed logs
3. **Application Logs**: View logs in Railway dashboard or local console

## Troubleshooting

### Common Issues

**Issue**: Notifications not being sent
- Check that `STAFF_PHONE_NUMBERS` is configured correctly
- Verify Twilio credentials are valid
- Check Twilio account balance

**Issue**: Tasks not syncing from Albiware
- Verify Albiware API key is correct
- Check Albiware API rate limits
- Review system logs for errors

**Issue**: Database connection errors
- Verify `DATABASE_URL` is correct
- Ensure PostgreSQL service is running
- Check database credentials

## Support

For issues related to:
- **Albiware API**: Contact Albiware support
- **Twilio SMS**: Contact Twilio support
- **Railway Deployment**: Contact Railway support

## License

Copyright © 2026 Lifeline Restoration. All rights reserved.
