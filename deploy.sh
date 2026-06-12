#!/bin/bash
# Nemo Cloud Deployment Script — run this in Google Cloud Shell.
# Prerequisites: GCP project created, billing enabled.
# Run: bash deploy.sh

set -e

PROJECT_ID="${1:-nemo-market-bot}"
REGION="us-central1"
REPO="nemo"

echo "=== Step 1: Set project ==="
gcloud config set project "$PROJECT_ID"

echo "=== Step 2: Enable APIs ==="
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com

echo "=== Step 3: Create Artifact Registry repo ==="
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --description="Nemo bot images" || echo "Repo may already exist"

echo "=== Step 4: Authenticate Docker ==="
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

echo "=== Step 5: Build with Cloud Build ==="
gcloud builds submit --config cloudbuild.yaml --project="$PROJECT_ID"

echo "=== Step 6: Get the service URL ==="
URL=$(gcloud run services describe nemo-bot \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')
echo "Service URL: $URL"

echo ""
echo "=== DONE ==="
echo "Set up Google Chat bot with endpoint: $URL/chat"
echo "Set up Telegram webhook with: curl https://api.telegram.org/bot<TOKEN>/setWebhook?url=$URL/telegram"
echo "Create Cloud Scheduler jobs:"
echo "  - 08:55 IST -> $URL/morning-brief"
echo "  - 09:20 IST -> $URL/first-signal"
echo "  - Every 15 min (market hours) -> $URL/scan"
