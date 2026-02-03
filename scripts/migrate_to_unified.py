#!/usr/bin/env python3
"""Migration script: Add mode field to existing jobs and timelines.

This script migrates existing data to the unified video factory architecture:
- Adds mode="learning" to all existing jobs
- Adds mode="learning" to all existing timelines
- Initializes default learning_config for jobs without it

Usage:
    python scripts/migrate_to_unified.py [--dry-run]

Options:
    --dry-run    Show what would be changed without making actual changes
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def migrate_jobs(jobs_dir: Path, dry_run: bool = False) -> int:
    """Migrate job meta.json files to add mode field.

    Returns number of jobs migrated.
    """
    migrated = 0

    for job_dir in jobs_dir.iterdir():
        if not job_dir.is_dir():
            continue

        meta_file = job_dir / "meta.json"
        if not meta_file.exists():
            continue

        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check if already migrated
        if "mode" in data and data["mode"]:
            continue

        # Add mode and default config
        data["mode"] = "learning"
        if "learning_config" not in data or data["learning_config"] is None:
            data["learning_config"] = {
                "subtitle_style": "half_screen",
                "generate_cards": True,
                "card_types": ["word", "entity"],
            }

        if dry_run:
            print(f"[DRY RUN] Would migrate job: {job_dir.name}")
        else:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Migrated job: {job_dir.name}")

        migrated += 1

    return migrated


def migrate_timelines(timelines_dir: Path, dry_run: bool = False) -> int:
    """Migrate timeline JSON files to add mode field.

    Returns number of timelines migrated.
    """
    migrated = 0

    for timeline_file in timelines_dir.glob("*.json"):
        with open(timeline_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check if already migrated
        if "mode" in data and data["mode"]:
            continue

        # Add mode
        data["mode"] = "learning"

        if dry_run:
            print(f"[DRY RUN] Would migrate timeline: {timeline_file.name}")
        else:
            with open(timeline_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Migrated timeline: {timeline_file.name}")

        migrated += 1

    return migrated


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN MODE ===\n")

    # Determine paths
    base_dir = Path(__file__).parent.parent
    jobs_dir = base_dir / "jobs"
    data_dir = base_dir / "data"
    timelines_dir = data_dir / "timelines"

    print(f"Jobs directory: {jobs_dir}")
    print(f"Timelines directory: {timelines_dir}\n")

    # Migrate jobs
    if jobs_dir.exists():
        jobs_migrated = migrate_jobs(jobs_dir, dry_run)
        print(f"\nJobs migrated: {jobs_migrated}")
    else:
        print("Jobs directory not found, skipping job migration")
        jobs_migrated = 0

    # Migrate timelines
    if timelines_dir.exists():
        timelines_migrated = migrate_timelines(timelines_dir, dry_run)
        print(f"Timelines migrated: {timelines_migrated}")
    else:
        print("Timelines directory not found, skipping timeline migration")
        timelines_migrated = 0

    # Summary
    total = jobs_migrated + timelines_migrated
    if dry_run:
        print(f"\n=== DRY RUN COMPLETE ===")
        print(f"Would migrate {total} items (jobs: {jobs_migrated}, timelines: {timelines_migrated})")
        print("Run without --dry-run to apply changes.")
    else:
        print(f"\n=== MIGRATION COMPLETE ===")
        print(f"Migrated {total} items (jobs: {jobs_migrated}, timelines: {timelines_migrated})")


if __name__ == "__main__":
    main()
