# Hardcore Player v2 n8n Workflows

This directory contains n8n workflow templates for the Hardcore Player v2 architecture.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Fetcher Layer                        │
├─────────────────────────────────────────────────────────┤
│  youtube_channel.json  ─┐                               │
│  youtube_playlist.json ─┼─► Detect new content → Items  │
│  rss.json              ─┤                               │
│  podcast.json          ─┘                               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                    Fan-out Layer                        │
├─────────────────────────────────────────────────────────┤
│  trigger_pipelines.json                                 │
│  New Item → Get Source config → Trigger Pipelines       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   Notify/Ops Layer                      │
├─────────────────────────────────────────────────────────┤
│  completion.json  - Pipeline completion notifications   │
│  failure.json     - Failure alerts                      │
│  daily_report.json - Daily statistics report            │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
workflows/
├── fetchers/           # Content source fetchers
│   ├── youtube_channel.json
│   ├── rss.json
│   └── podcast.json
├── fanout/             # Pipeline triggering
│   └── trigger_pipelines.json
├── notify/             # Notifications and ops
│   ├── completion.json
│   ├── failure.json
│   └── daily_report.json
└── _archive_v1/        # Deprecated v1 workflows (for reference)
    ├── hardcore-player_pipeline.json
    ├── hardcore-player_batch.json
    └── hardcore-player_monitor.json
```

> **Note:** The `_archive_v1/` folder contains deprecated v1 workflows. These are kept for reference only and should not be used with v2.

## Configuration

### Environment Variables

Set these in n8n:
- `API_URL`: Hardcore Player API base URL (e.g., `http://localhost:8000`)
- `NOTIFICATION_WEBHOOK`: Slack/Discord webhook URL for notifications

### Importing Workflows

1. Open n8n
2. Go to Workflows → Import from File
3. Select the JSON file
4. Configure credentials and environment variables
5. Activate the workflow

## Workflow Details

### Fetchers

Each fetcher runs on a schedule and:
1. Fetches enabled sources from Hardcore Player API
2. Checks for new content from each source
3. Creates Items for new content
4. Optionally triggers the fanout workflow

| Workflow | Schedule | Source Types |
|----------|----------|--------------|
| youtube_channel.json | Every 15 min | YouTube channels |
| youtube_playlist.json | Every 30 min | YouTube playlists |
| rss.json | Every 30 min | RSS/Atom feeds |
| podcast.json | Every 1 hour | Podcast RSS |

### Fan-out

`trigger_pipelines.json` is triggered via webhook when a new Item is created:
1. Receives Item ID from webhook
2. Fetches Item and Source details
3. Loops through Source's default_pipelines
4. Creates a Job for each pipeline

### Notifications

- `completion.json`: Triggered when a Job completes, sends success notification
- `failure.json`: Triggered when a Job fails, sends alert
- `daily_report.json`: Runs daily, fetches stats and sends summary
