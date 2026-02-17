# Complete SMS Automation Process

## Overview

This document outlines the entire SMS conversation flow from lead creation to project completion, including all automated steps and notifications.

---

## Phase 1: Lead Creation & Initial Setup

### Step 1: New Lead Created in Albiware
- Customer fills out form on website
- Lead is created in Albiware
- System syncs lead to local database as a `Contact`

### Step 2: 24-Hour Wait Period
- System waits 24 hours after lead creation
- Allows time for initial contact attempt by staff
- Contact status: `NEW` → `FOLLOW_UP_SCHEDULED`

---

## Phase 2: Initial Follow-Up SMS

### Step 3: Initial SMS Sent to Technician
**Trigger:** 24 hours after lead creation

**Message:**
```
Hi Rudy, were you able to make contact with [Customer Name] yet? Reply YES or NO.
```

**Contact Status:** `FOLLOW_UP_SENT` → `AWAITING_RESPONSE`

**Conversation State:** `AWAITING_CONTACT_CONFIRMATION`

---

## Phase 3: Conversation Flow - Contact Confirmation

### Step 4a: Technician Replies "YES"
**Technician Response:** `YES` (or yes, y, Y)

**System Action:**
- Records contact was made
- Contact status: `CONTACT_MADE`
- Conversation state: `AWAITING_OUTCOME`

**Next SMS:**
```
Great! What was the outcome with [Customer Name]?

1 - Appointment set
2 - Looking for quotes
3 - Waste of time
4 - Something else
```

---

### Step 4b: Technician Replies "NO"
**Technician Response:** `NO` (or no, n, N)

**System Action:**
- Records no contact made
- Contact status: `NO_CONTACT`
- Conversation state: `COMPLETED`

**Next SMS:**
```
Got it. I'll check back with you in a few days about [Customer Name].
```

**End of conversation** (for now)

---

## Phase 4: Outcome Collection

### Step 5: Technician Selects Outcome

#### Option 1: "Appointment Set"
**Technician Response:** `1`

**System Action:**
- Records outcome: `APPOINTMENT_SET`
- Sets `project_creation_needed = True`
- Conversation state: `AWAITING_PROJECT_TYPE`

**Next SMS:**
```
Great! I need a few details to create the project for [Customer Name]. What type of project?

1 - Emergency Mitigation Services
2 - Mold
3 - Reconstruction
4 - Sewage
5 - Biohazard
6 - Contents
7 - Vandalism
```

**→ Continues to Phase 5: Project Details Collection**

---

#### Option 2: "Looking for Quotes"
**Technician Response:** `2`

**System Action:**
- Records outcome: `LOOKING_FOR_QUOTES`
- Contact status: `COMPLETED`
- Conversation state: `COMPLETED`

**Next SMS:**
```
Thanks for the update. I'll mark [Customer Name] as looking for quotes.
```

**End of conversation**

---

#### Option 3: "Waste of Time"
**Technician Response:** `3`

**System Action:**
- Records outcome: `WASTE_OF_TIME`
- Contact status: `COMPLETED`
- Conversation state: `COMPLETED`

**Next SMS:**
```
Got it. I'll mark [Customer Name] accordingly.
```

**End of conversation**

---

#### Option 4: "Something Else"
**Technician Response:** `4`

**System Action:**
- Records outcome: `SOMETHING_ELSE`
- Contact status: `COMPLETED`
- Conversation state: `COMPLETED`

**Next SMS:**
```
Thanks for letting me know. I've updated [Customer Name]'s status.
```

**End of conversation**

---

## Phase 5: Project Details Collection

### Step 6: Project Type
**Conversation State:** `AWAITING_PROJECT_TYPE`

**SMS:**
```
Great! I need a few details to create the project for [Customer Name]. What type of project?

1 - Emergency Mitigation Services
2 - Mold
3 - Reconstruction
4 - Sewage
5 - Biohazard
6 - Contents
7 - Vandalism
```

**Technician Response:** `1-7`

**System Action:**
- Stores `project_type`
- Conversation state: `AWAITING_PROPERTY_TYPE`

---

### Step 7: Property Type
**Conversation State:** `AWAITING_PROPERTY_TYPE`

**SMS:**
```
What type of property?

1 - Residential
2 - Commercial
```

**Technician Response:** `1` or `2`

**System Action:**
- Stores `property_type`
- **IF Residential** → Conversation state: `AWAITING_RESIDENTIAL_SUBTYPE`
- **IF Commercial** → Conversation state: `AWAITING_INSURANCE`

---

### Step 7.5: Residential Subtype (IF Residential)
**Conversation State:** `AWAITING_RESIDENTIAL_SUBTYPE`

**SMS:**
```
What type of residential property?

1 - Single Family Home
2 - Multi-Family Home
3 - Manufactured Home
```

**Technician Response:** `1`, `2`, or `3`

**System Action:**
- Stores `residential_subtype`
- Conversation state: `AWAITING_INSURANCE`

---

### Step 8: Insurance
**Conversation State:** `AWAITING_INSURANCE`

**SMS:**
```
Do they have insurance? Reply YES or NO
```

**Technician Response:** `YES` or `NO`

**System Action:**
- Stores `has_insurance = True/False`
- **IF YES** → Conversation state: `AWAITING_INSURANCE_COMPANY`
- **IF NO** → Conversation state: `AWAITING_REFERRAL_SOURCE`

---

### Step 9: Insurance Company (IF has insurance)
**Conversation State:** `AWAITING_INSURANCE_COMPANY`

**SMS:**
```
What insurance company?
```

**Technician Response:** Free text (e.g., "State Farm")

**System Action:**
- Stores `insurance_company`
- Conversation state: `AWAITING_REFERRAL_SOURCE`

---

### Step 10: Referral Source
**Conversation State:** `AWAITING_REFERRAL_SOURCE`

**SMS:**
```
How did they hear about us?

1 - Lead Gen
2 - Customer Referral
3 - Insurance Referral
4 - Online Marketing
5 - Agent
6 - Industry Partner
7 - Plumber
8 - Vehicle Wraps
```

**Technician Response:** `1-8`

**System Action:**
- Stores `referral_source`
- Conversation state: `COMPLETED`

---

### Step 11: Final Confirmation
**SMS:**
```
Perfect! I have all the details for [Customer Name]:

• Project: [Project Type]
• Property: [Property Type] - [Residential Subtype if applicable]
• Insurance: [Yes/No + Company if applicable]
• Source: [Referral Source]

I'll create the project in Albiware now. You'll get a confirmation once it's done!
```

**System Action:**
- Contact status: `COMPLETED`
- `project_creation_needed = True`
- Ready for automation to create project

---

## Phase 6: Automated Project Creation

### Step 12: Project Creation Automation Triggers
**Trigger:** Scheduled task checks for contacts with `project_creation_needed = True`

**System Actions:**
1. Logs into Albiware
2. Navigates to Project Creation form
3. Fills out form with collected data:
   - Customer (from Albiware contact)
   - Referrer Option: "Add Existing"
   - Referral Sources: [Selected source]
   - Project Type: [Selected type]
   - Property Type: [Selected type]
   - **Year Built: [Auto-filled from property API]**
   - Staff: Rodolfo Arceo
   - Project Role: Estimator
   - Insurance Info: [Yes/No]
4. Submits form
5. Verifies project creation
6. Extracts Albiware Project ID

---

### Step 13: Property Year Built Lookup (IF ENABLED)
**Trigger:** During project creation, after Property Type is set

**System Actions:**
1. Gets customer address from Albiware contact
2. Calls Real-Time Real-Estate Data API
3. Extracts `year_built` from response
4. Auto-fills "Year Built" field in form

**Logs:**
```
Looking up year built for address: [Address]
Successfully retrieved property data
Year built: [Year]
✓ Year Built: [Year]
```

---

### Step 14: Asbestos Testing Check (IF year_built < 1988)
**Trigger:** After year built is retrieved and `year_built < 1988`

**System Actions:**
1. Sets `asbestos_testing_required = True`
2. Records `asbestos_notification_sent_at`
3. Sends SMS to technician

**SMS to Technician:**
```
⚠️ ASBESTOS TESTING REQUIRED

Property: [Customer Name]
Address: [Property Address]
Year Built: [Year]

This property was built before 1988 and requires asbestos testing before work begins.
```

**Logs:**
```
Property built in [Year] (pre-1988) - Asbestos testing required
✅ Asbestos notification sent to [Phone Number]
```

---

### Step 15: Project Creation Success
**System Actions:**
1. Sets `project_created = True`
2. Sets `albiware_project_id = [ID]`
3. Sets `project_created_at = [timestamp]`
4. Logs success

**Logs:**
```
✅ Successfully created project [ID] for [Customer Name]
```

---

## Phase 7: Post-Creation Notifications

### Step 16: Project Creation Confirmation SMS
**Trigger:** After successful project creation

**SMS to Technician:**
```
✅ Project created for [Customer Name]!

Project ID: [Albiware Project ID]
Type: [Project Type]
Property: [Property Type]

You can view it in Albiware now.
```

---

## Summary of SMS Messages

### To Technician:
1. **Initial Follow-Up** (24 hours after lead)
2. **Outcome Request** (after YES response)
3. **Project Type Question** (if appointment set)
4. **Property Type Question**
5. **Residential Subtype Question** (if residential)
6. **Insurance Question**
7. **Insurance Company Question** (if has insurance)
8. **Referral Source Question**
9. **Final Confirmation** (with all details)
10. **Asbestos Warning** (if property built before 1988)
11. **Project Creation Success** (after automation completes)

---

## Feature Flags & Configuration

### Property Lookup (Year Built)
```bash
ENABLE_PROPERTY_LOOKUP=false  # Disabled by default (testing)
ENABLE_PROPERTY_LOOKUP=true   # Enable for production
```

**When Disabled:**
- No API calls made
- No API credits used
- Year Built field left empty
- No asbestos notifications

**When Enabled:**
- Automatic year built lookup
- Auto-fills Year Built field
- Triggers asbestos notifications for pre-1988 properties
- Uses 1 API credit per project (100 free/month)

---

## Database Tracking

### Contact Fields Updated:
- `status` - Current status in workflow
- `outcome` - Result of contact attempt
- `conversation_state` - Current SMS conversation state
- `project_type` - Selected project type
- `property_type` - Residential or Commercial
- `residential_subtype` - Type of residential property
- `has_insurance` - Boolean
- `insurance_company` - Company name
- `referral_source` - How they heard about us
- `project_creation_needed` - Boolean flag
- `project_created` - Boolean flag
- `albiware_project_id` - Created project ID
- `asbestos_testing_required` - Boolean flag
- `asbestos_notification_sent_at` - Timestamp

---

## Error Handling

### If Project Creation Fails:
1. Logs error details
2. Marks `project_creation_needed = True` (stays true)
3. Will retry on next automation run
4. Technician NOT notified of failure (only success)

### If Property API Fails:
1. Logs warning
2. Continues with project creation
3. Year Built field left empty
4. No asbestos notification sent

### If SMS Fails:
1. Logs error
2. Continues with automation
3. Does not block project creation

---

## Testing Recommendations

### Phase 1: Test SMS Conversation (Current)
- Property lookup: **DISABLED**
- Test full conversation flow
- Verify all questions and responses
- Check database updates

### Phase 2: Test Project Creation (Current)
- Property lookup: **DISABLED**
- Verify form filling works
- Check project is created in Albiware
- Verify success notification

### Phase 3: Enable Property Lookup (Production)
- Set `ENABLE_PROPERTY_LOOKUP=true`
- Monitor API usage
- Verify year built auto-fill
- Test asbestos notifications

---

## API Credits Usage

### Real-Time Real-Estate Data API:
- **Free Tier:** 100 requests/month
- **Cost per request:** $0 (free tier)
- **Rate limit:** 1 request per minute
- **Current usage:** 0 (feature disabled)

### Twilio SMS:
- **Cost per SMS:** ~$0.0075
- **Estimated monthly cost:** 
  - 50 leads/month × 11 SMS avg = 550 SMS = **~$4.13/month**
  - 100 leads/month × 11 SMS avg = 1,100 SMS = **~$8.25/month**
