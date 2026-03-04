"""
Vapi Webhook Server → Google Docs Logger
Receives Vapi end-of-call-report events and appends a formatted
summary to a specified Google Doc.

Deploy on Google Cloud Run (see README.md for instructions).
"""

import os
import hmac
import hashlib
import json
from datetime import datetime, timezone

from flask import Flask, request, jsonify, abort
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# ── Config (set these as environment variables) ──────────────────────────────
VAPI_WEBHOOK_SECRET = os.environ.get("VAPI_WEBHOOK_SECRET", "")   # optional but recommended
GOOGLE_DOC_ID       = os.environ.get("GOOGLE_DOC_ID", "")         # ID from the Google Doc URL
SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_JSON", "") # JSON string of service account creds
# ─────────────────────────────────────────────────────────────────────────────


def get_docs_service():
    """Build authenticated Google Docs API client from service account JSON."""
    if not SERVICE_ACCOUNT_JSON:
        raise RuntimeError("SERVICE_ACCOUNT_JSON environment variable is not set.")
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/documents"],
    )
    return build("docs", "v1", credentials=creds)


def verify_signature(request) -> bool:
    """Verify Vapi webhook signature (HMAC-SHA256). Skips check if no secret set."""
    if not VAPI_WEBHOOK_SECRET:
        return True  # signature verification disabled
    signature = request.headers.get("x-vapi-signature", "")
    payload   = request.get_data()
    expected  = hmac.new(
        VAPI_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def format_call_entry(report: dict) -> str:
    """Format an end-of-call report into a readable text block."""
    call     = report.get("call", {})
    ts       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    duration = report.get("durationSeconds", 0)
    cost     = report.get("cost", 0)
    summary  = report.get("summary", "No summary provided.")
    transcript = report.get("transcript", "No transcript available.")

    minutes, seconds = divmod(int(duration), 60)

    lines = [
        "─" * 60,
        f"📞  Call Log  |  {ts}",
        "─" * 60,
        f"Call ID   : {call.get('id', 'N/A')}",
        f"Duration  : {minutes}m {seconds}s",
        f"Cost      : ${cost:.4f}",
        f"Status    : {call.get('status', 'N/A')}",
        "",
        "── Summary ─────────────────────────────────────────────",
        summary,
        "",
        "── Transcript ──────────────────────────────────────────",
        transcript,
        "",
    ]
    return "\n".join(lines)


def append_to_doc(text: str):
    """Append text to the end of the configured Google Doc."""
    if not GOOGLE_DOC_ID:
        raise RuntimeError("GOOGLE_DOC_ID environment variable is not set.")

    service = get_docs_service()

    # Get current end index of document body
    doc = service.documents().get(documentId=GOOGLE_DOC_ID).execute()
    body_content = doc.get("body", {}).get("content", [])
    end_index = body_content[-1].get("endIndex", 1) - 1  # before the final \n

    requests_body = [
        {
            "insertText": {
                "location": {"index": end_index},
                "text": "\n" + text,
            }
        }
    ]
    service.documents().batchUpdate(
        documentId=GOOGLE_DOC_ID,
        body={"requests": requests_body},
    ).execute()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "vapi-webhook-logger"}), 200


@app.route("/vapi/webhook", methods=["POST"])
def vapi_webhook():
    # 1. Verify signature
    if not verify_signature(request):
        abort(401, "Invalid webhook signature")

    data    = request.get_json(silent=True) or {}
    message = data.get("message", {})
    msg_type = message.get("type", "")

    # 2. Only handle end-of-call-report
    if msg_type != "end-of-call-report":
        return jsonify({"received": True, "processed": False}), 200

    # 3. Format and append to Google Doc
    try:
        entry = format_call_entry(message)
        append_to_doc(entry)
        print(f"[OK] Logged call {message.get('call', {}).get('id')} to Google Doc")
    except Exception as e:
        print(f"[ERROR] Failed to write to Google Doc: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify({"received": True, "processed": True}), 200


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
