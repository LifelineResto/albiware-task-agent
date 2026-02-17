# Property Lookup Feature

## Overview

The property lookup feature automatically retrieves property data (including year built) from the Real-Time Real-Estate Data API when creating projects in Albiware.

## How It Works

1. After technician confirms appointment and provides project details via SMS
2. Automation triggers project creation in Albiware
3. System retrieves customer address from Albiware contact
4. Calls Real-Time Real-Estate Data API to get property information
5. Extracts year built from API response
6. Auto-fills "Year Built" field in project creation form (if field exists)

## Feature Flag

The property lookup is controlled by an environment variable to avoid using API credits during testing:

```bash
ENABLE_PROPERTY_LOOKUP=false  # Disabled (default for testing)
ENABLE_PROPERTY_LOOKUP=true   # Enabled (for production)
```

## API Details

- **Provider**: Real-Time Real-Estate Data API (RapidAPI)
- **Endpoint**: `/property-details-address`
- **Pricing**: 
  - FREE: 100 requests/month
  - Pro: $25/month for 10,000 requests
- **Rate Limit**: 1 request per minute (free tier)

## Configuration

### Environment Variables

Add these to your Railway environment variables:

```bash
ENABLE_PROPERTY_LOOKUP=false
RAPIDAPI_KEY=6f5f7bf2ddmsha07dd01ac88dee3p127f46jsn46a46ee09c85
```

### Enabling for Production

When ready to use the property lookup in production:

1. Go to Railway dashboard
2. Select the albiware-task-agent service
3. Go to Variables tab
4. Change `ENABLE_PROPERTY_LOOKUP` from `false` to `true`
5. Save and redeploy

## Testing

### With Feature Disabled (Current State)

```bash
ENABLE_PROPERTY_LOOKUP=false
```

- Property lookup will NOT be called
- No API credits used
- Logs will show: "Property lookup DISABLED (feature flag)"
- Year Built field will be left empty (or use default value)

### With Feature Enabled

```bash
ENABLE_PROPERTY_LOOKUP=true
```

- Property lookup will be called for each project creation
- Uses 1 API credit per project
- Logs will show: "Looking up property data for address: [address]"
- Year Built field will be auto-filled if found

## Logs

Check Railway logs for property lookup activity:

```
✓ Property Type: Residential
STEP 4.5: Year Built (property API lookup)...
Looking up year built for address: 7151 S Durango Dr Unit 303 Las Vegas NV 89113
Successfully retrieved property data for 7151 S Durango Dr Unit 303 Las Vegas NV 89113
Year built for 7151 S Durango Dr Unit 303 Las Vegas NV 89113: 2002
✓ Year Built: 2002
```

## API Credits Usage

- Free tier: 100 requests/month
- Current usage: 0 (feature disabled)
- Monitor at: https://rapidapi.com/developer/billing

## Troubleshooting

### Property lookup not working?

1. Check `ENABLE_PROPERTY_LOOKUP` is set to `true`
2. Verify `RAPIDAPI_KEY` is correct
3. Check Railway logs for error messages
4. Verify customer has address in Albiware
5. Check API credit balance

### Year Built field not filled?

1. Field may not exist on Albiware project creation form
2. Property data may not be available for that address
3. API may have timed out (check logs)

## Files

- `services/property_lookup.py` - Property API service
- `services/project_creator.py` - Integration with project creation
- `.env.example` - Environment variable template
