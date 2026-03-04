# Vapi → Google Docs Call Logger

A webhook server that receives Vapi `end-of-call-report` events and appends a formatted call summary to a Google Doc.

## How It Works

```
Vapi call ends → Vapi POSTs to your webhook → Server formats the report → Appends to Google Doc
```

---

## Setup Guide

### Step 1: Create a Google Doc

1. Go to [Google Docs](https://docs.google.com) and create a new doc (e.g. "Vapi Call Log")
2. Copy the **Document ID** from the URL:
   ```
   https://docs.google.com/document/d/YOUR_DOC_ID_HERE/edit
   ```

---

### Step 2: Create a Google Service Account

Your webhook server needs permission to write to the Google Doc. A service account handles this.

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable the **Google Docs API**:
   - APIs & Services → Library → search "Google Docs API" → Enable
4. Create a Service Account:
   - APIs & Services → Credentials → Create Credentials → Service Account
   - Give it a name (e.g. `vapi-webhook`)
   - Click Done
5. Generate a key:
   - Click the service account → Keys tab → Add Key → JSON
   - Download the JSON file — this is your `SERVICE_ACCOUNT_JSON`
6. **Share your Google Doc** with the service account email (looks like `vapi-webhook@your-project.iam.gserviceaccount.com`):
   - Open the Google Doc → Share → paste the service account email → Editor access

---

### Step 3: Deploy to Google Cloud Run

Make sure you have the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated.

```bash
# 1. Set your project
gcloud config set project YOUR_PROJECT_ID

# 2. Build and deploy
gcloud run deploy vapi-webhook-logger \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_DOC_ID=YOUR_DOC_ID" \
  --set-env-vars "VAPI_WEBHOOK_SECRET=your-chosen-secret" \
  --set-env-vars "SERVICE_ACCOUNT_JSON=$(cat your-service-account.json | tr -d '\n')"
```

3. After deployment, copy the service URL — it looks like:
   ```
   https://vapi-webhook-logger-xxxx-uc.a.run.app
   ```

---

### Step 4: Configure Vapi to Send Events to Your Webhook

Set the server URL at the **organization level** (applies to all calls) in the Vapi Dashboard:

👉 **Settings → Server URL** → paste your Cloud Run URL + `/vapi/webhook`

```
https://vapi-webhook-logger-xxxx-uc.a.run.app/vapi/webhook
```

Or configure it on a specific assistant via the API:

```bash
curl -X PATCH https://api.vapi.ai/assistant/YOUR_ASSISTANT_ID \
  -H "Authorization: Bearer your-vapi-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "serverUrl": "https://your-cloud-run-url/vapi/webhook",
    "serverUrlSecret": "your-chosen-secret"
  }'
```

---

## What Gets Logged

Each call appends a block like this to your Google Doc:

```
────────────────────────────────────────────────────────────
📞  Call Log  |  2026-03-03 14:22 UTC
────────────────────────────────────────────────────────────
Call ID   : call_abc123
Duration  : 3m 47s
Cost      : $0.0842
Status    : ended

── Summary ─────────────────────────────────────────────────
The caller asked about pricing for the enterprise plan...

── Transcript ──────────────────────────────────────────────
[user]: Hi, I'd like to know more about pricing...
[assistant]: Of course! Our enterprise plan starts at...
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_DOC_ID` | ✅ | ID from your Google Doc URL |
| `SERVICE_ACCOUNT_JSON` | ✅ | Full service account credentials JSON |
| `VAPI_WEBHOOK_SECRET` | Recommended | Secret for verifying webhook requests |
| `VAPI_API_KEY` | Optional | Your Vapi API key (for future use) |

---

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set env vars
export GOOGLE_DOC_ID="your-doc-id"
export SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
export VAPI_WEBHOOK_SECRET=""   # leave empty to skip verification locally

# Run the server
python main.py

# In another terminal, simulate a Vapi webhook:
curl -X POST http://localhost:8080/vapi/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "end-of-call-report",
      "call": {"id": "test-call-001", "status": "ended"},
      "durationSeconds": 125,
      "cost": 0.042,
      "summary": "Test call summary.",
      "transcript": "[user]: Hello\n[assistant]: Hi there!"
    }
  }'
```

---

## Files

```
vapi-webhook/
├── main.py           # Flask webhook server
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container config for Cloud Run
├── .env.example      # Environment variable template
└── README.md         # This guide
```
