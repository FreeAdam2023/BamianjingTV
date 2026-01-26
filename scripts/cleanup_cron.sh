#!/bin/bash
# Automatic cleanup script for old job files
# Add to crontab: 0 3 * * * /path/to/cleanup_cron.sh
#
# This runs at 3 AM daily and removes video files older than 30 days

API_URL="${API_URL:-http://localhost:8000}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

echo "[$(date)] Starting cleanup (retention: ${RETENTION_DAYS} days)"

# Run cleanup (videos_only=true to keep metadata, dry_run=false to actually delete)
curl -s -X POST "${API_URL}/admin/cleanup" \
  -H "Content-Type: application/json" \
  -d "{
    \"retention_days\": ${RETENTION_DAYS},
    \"videos_only\": true,
    \"dry_run\": false
  }" | jq .

echo "[$(date)] Cleanup complete"
