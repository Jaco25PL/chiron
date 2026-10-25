#!/usr/bin/env bash
# Deploys the backend to Cloud Run (scale to zero = free tier) with secrets from Secret Manager.
#
# One-time setup (needs billing linked to the project):
#   gcloud auth login
#   gcloud config set project chiron-512703
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
#   deploy/cloudrun.sh secrets      # uploads values from .env to Secret Manager
#
# Every deploy:
#   deploy/cloudrun.sh
set -euo pipefail

PROJECT=chiron-512703
REGION=southamerica-east1          # São Paulo, same region as the Neon database
SERVICE=chiron-api
SECRETS=(GOOGLE_API_KEY_1 GOOGLE_API_KEY_2 GOOGLE_API_KEY_3 DATABASE_URL CHIRON_BACKEND_SECRET LANGSMITH_API_KEY)

cd "$(dirname "$0")/.."

if [[ "${1:-}" == "secrets" ]]; then
  for name in "${SECRETS[@]}"; do
    value=$(grep -E "^${name}=" .env | cut -d= -f2-)
    [[ -z "$value" ]] && { echo "skip $name (not in .env)"; continue; }
    if gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1; then
      printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --project "$PROJECT"
    else
      printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic --project "$PROJECT"
    fi
  done
  # the Cloud Run runtime service account must be able to read them
  sa="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
  for name in "${SECRETS[@]}"; do
    gcloud secrets add-iam-policy-binding "$name" --member="serviceAccount:$sa" \
      --role=roles/secretmanager.secretAccessor --project "$PROJECT" >/dev/null 2>&1 || true
  done
  exit 0
fi

secret_flags=$(for n in "${SECRETS[@]}"; do printf '%s=%s:latest,' "$n" "$n"; done | sed 's/,$//')

gcloud run deploy "$SERVICE" \
  --project "$PROJECT" --region "$REGION" --source . \
  --allow-unauthenticated \
  --min-instances 0 --max-instances 2 \
  --cpu 1 --memory 1Gi --timeout 120 --concurrency 20 \
  --set-env-vars "LANGSMITH_TRACING=true,LANGSMITH_PROJECT=chiron" \
  --set-secrets "$secret_flags"
