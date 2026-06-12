#!/bin/bash
set -e

PROJECT_ID="${1:-nemo-market-bot}"
REGION="us-central1"
REPO="nemo"
SVC="nemo-bot"

echo "=========================================="
echo " Nemo Cloud — Full Deployment"
echo " Project: $PROJECT_ID"
echo " Region: $REGION"
echo "=========================================="

echo ""
echo "=== Step 1/9: Set project ==="
gcloud config set project "$PROJECT_ID" --quiet

echo ""
echo "=== Step 2/9: Enable APIs ==="
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com

echo ""
echo "=== Step 3/9: Create credentials.env ==="
if [ ! -f credentials.env ]; then
  cat > credentials.env << 'ENDCRED'
TELEGRAM_TOKEN=8028776380:AAFH-MwDgVf_JwsgCCqXMVq7lrjSlAVgCVI
TELEGRAM_CHAT_ID=446307019
GEMINI_API_KEY=AIzaSyA_JYyCqXLj8RmUHC4XcIzlIc1gsqwb0tM
GMAIL_USER=neptune.works.hard@gmail.com
GMAIL_APP_PASSWORD=algv wszg zwdj wvlw
EMAIL_TO=houseneptune0@gmail.com
ENDCRED
  echo "Created credentials.env"
fi

echo ""
echo "=== Step 4/9: Create Artifact Registry repo ==="
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --description="Nemo bot images" 2>/dev/null || echo "Repo already exists"

echo ""
echo "=== Step 5/9: Build and push container ==="
gcloud builds submit --config cloudbuild.yaml --project="$PROJECT_ID"

IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/nemo-bot:latest"

echo ""
echo "=== Step 6/9: Deploy to Cloud Run ==="
gcloud run deploy "$SVC" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=1Gi \
  --timeout=300 \
  --min-instances=0 \
  --max-instances=1 \
  --concurrency=1

URL=$(gcloud run services describe "$SVC" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')
echo "Service URL: $URL"

echo ""
echo "=== Step 7/9: Set Telegram webhook ==="
TOKEN="8028776380:AAFH-MwDgVf_JwsgCCqXMVq7lrjSlAVgCVI"
curl -s -X POST "https://api.telegram.org/bot$TOKEN/setWebhook?url=$URL/telegram" > /dev/null
echo "Telegram webhook set to $URL/telegram"

echo ""
echo "=== Step 8/9: Create Cloud Scheduler jobs ==="
# Morning brief — 8:55 AM IST = 3:25 AM UTC
gcloud scheduler jobs create http nemo-morning-brief \
  --schedule="25 3 * * 1-5" \
  --uri="$URL/morning-brief" \
  --http-method=GET \
  --location="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || echo "Scheduler job nemo-morning-brief exists"

# First signal — 9:20 AM IST = 3:50 AM UTC
gcloud scheduler jobs create http nemo-first-signal \
  --schedule="50 3 * * 1-5" \
  --uri="$URL/first-signal" \
  --http-method=GET \
  --location="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || echo "Scheduler job nemo-first-signal exists"

# Continuous scan — every 15 min during market hours (9:15-15:30 IST = 3:45-10:00 UTC)
gcloud scheduler jobs create http nemo-scan \
  --schedule="*/15 3-10 * * 1-5" \
  --uri="$URL/scan" \
  --http-method=GET \
  --location="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || echo "Scheduler job nemo-scan exists"

echo ""
echo "=== Step 9/9: Google Chat bot config ==="
echo ""
echo "==========================================="
echo " DEPLOYMENT COMPLETE"
echo "==========================================="
echo ""
echo "Service URL: $URL"
echo ""
echo "--- Google Chat Bot Setup ---"
echo "1. Open: https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat"
echo "2. Click: + CREATE APP"
echo "3. App Name: Nemo"
echo "4. Avatar URL: https://i.imgur.com/YOUR_BOT_IMAGE.png  (or leave blank)"
echo "5. Connection settings -> Google Cloud Run URL -> $URL/chat"
echo "6. Visibility: uncheck 'Publish app', leave as internal"
echo "7. Click CREATE"
echo "8. Now open Gmail -> Chat sidebar -> search Nemo -> message!"
echo ""
echo "--- Test ---"
echo "curl $URL        # Health check"
echo "curl $URL/chat   # Test chat endpoint"
echo "@NemoMarket_bot on Telegram is already active"
echo ""
echo "--- Daily schedule (IST) ---"
echo "08:55 Morning Brief"
echo "09:20 First Signal"
echo "09:15-15:30 Every 15 min scan"
