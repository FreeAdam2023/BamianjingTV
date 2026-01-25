"""Pipeline manager service for Hardcore Player."""

import json
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from app.config import settings
from app.models.pipeline import (
    PipelineConfig,
    PipelineType,
    PipelineCreate,
    PipelineUpdate,
    TargetConfig,
    TargetType,
    DEFAULT_PIPELINES,
)


class PipelineManager:
    """Manages pipeline configurations with JSON file persistence."""

    def __init__(self):
        self.pipelines: Dict[str, PipelineConfig] = {}
        self._load_pipelines()

    def _load_pipelines(self) -> None:
        """Load pipelines from JSON file on startup."""
        pipelines_file = settings.pipelines_file

        # Start with default pipelines
        for pipeline_id, pipeline in DEFAULT_PIPELINES.items():
            self.pipelines[pipeline_id] = pipeline

        if not pipelines_file.exists():
            logger.info("No existing pipelines file found, using defaults")
            self._save_pipelines()
            return

        try:
            with open(pipelines_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for pipeline_data in data.get("pipelines", []):
                # Convert target dict to TargetConfig
                if "target" in pipeline_data and isinstance(pipeline_data["target"], dict):
                    pipeline_data["target"] = TargetConfig(**pipeline_data["target"])
                pipeline = PipelineConfig(**pipeline_data)
                self.pipelines[pipeline.pipeline_id] = pipeline

            logger.info(f"Loaded {len(self.pipelines)} pipelines")
        except Exception as e:
            logger.error(f"Failed to load pipelines from {pipelines_file}: {e}")

    def _save_pipelines(self) -> None:
        """Save all pipelines to JSON file."""
        pipelines_file = settings.pipelines_file
        pipelines_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "pipelines": [
                pipeline.model_dump(mode="json")
                for pipeline in self.pipelines.values()
            ]
        }

        with open(pipelines_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def create_pipeline(self, pipeline_create: PipelineCreate) -> PipelineConfig:
        """Create a new pipeline configuration."""
        if pipeline_create.pipeline_id in self.pipelines:
            raise ValueError(f"Pipeline '{pipeline_create.pipeline_id}' already exists")

        pipeline = PipelineConfig(
            pipeline_id=pipeline_create.pipeline_id,
            pipeline_type=pipeline_create.pipeline_type,
            display_name=pipeline_create.display_name,
            target_language=pipeline_create.target_language,
            steps=pipeline_create.steps,
            generate_thumbnail=pipeline_create.generate_thumbnail,
            generate_content=pipeline_create.generate_content,
            target=pipeline_create.target,
            enabled=pipeline_create.enabled,
            created_at=datetime.now(),
        )

        self.pipelines[pipeline.pipeline_id] = pipeline
        self._save_pipelines()
        logger.info(f"Created pipeline: {pipeline.pipeline_id} ({pipeline.display_name})")
        return pipeline

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineConfig]:
        """Get a pipeline by ID."""
        return self.pipelines.get(pipeline_id)

    def list_pipelines(
        self,
        pipeline_type: Optional[PipelineType] = None,
        enabled_only: bool = False,
        limit: int = 100,
    ) -> List[PipelineConfig]:
        """List pipelines with optional filtering."""
        pipelines = list(self.pipelines.values())

        if pipeline_type:
            pipelines = [p for p in pipelines if p.pipeline_type == pipeline_type]

        if enabled_only:
            pipelines = [p for p in pipelines if p.enabled]

        # Sort by creation time, newest first
        pipelines.sort(key=lambda p: p.created_at, reverse=True)

        return pipelines[:limit]

    def update_pipeline(
        self,
        pipeline_id: str,
        pipeline_update: PipelineUpdate,
    ) -> Optional[PipelineConfig]:
        """Update an existing pipeline configuration."""
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline:
            return None

        # Apply updates
        update_data = pipeline_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(pipeline, field, value)

        self._save_pipelines()
        logger.info(f"Updated pipeline: {pipeline_id}")
        return pipeline

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a pipeline configuration."""
        # Prevent deleting default pipelines
        if pipeline_id in DEFAULT_PIPELINES:
            logger.warning(f"Cannot delete default pipeline: {pipeline_id}")
            return False

        pipeline = self.pipelines.pop(pipeline_id, None)
        if not pipeline:
            return False

        self._save_pipelines()
        logger.info(f"Deleted pipeline: {pipeline_id}")
        return True

    def get_pipelines_by_type(self) -> Dict[PipelineType, List[PipelineConfig]]:
        """Get pipelines grouped by type."""
        result: Dict[PipelineType, List[PipelineConfig]] = {}

        for pipeline in self.pipelines.values():
            if pipeline.pipeline_type not in result:
                result[pipeline.pipeline_type] = []
            result[pipeline.pipeline_type].append(pipeline)

        return result

    def get_pipelines_for_target(self, target_type: TargetType) -> List[PipelineConfig]:
        """Get all pipelines targeting a specific platform."""
        return [
            p for p in self.pipelines.values()
            if p.target.target_type == target_type and p.enabled
        ]

    def get_stats(self) -> Dict:
        """Get pipeline statistics."""
        stats = {
            "total": len(self.pipelines),
            "by_type": {},
            "by_target": {},
            "enabled": sum(1 for p in self.pipelines.values() if p.enabled),
        }

        for pipeline_type in PipelineType:
            count = sum(
                1 for p in self.pipelines.values()
                if p.pipeline_type == pipeline_type
            )
            if count > 0:
                stats["by_type"][pipeline_type.value] = count

        for target_type in TargetType:
            count = sum(
                1 for p in self.pipelines.values()
                if p.target.target_type == target_type
            )
            if count > 0:
                stats["by_target"][target_type.value] = count

        return stats


# Pipeline template helpers
def create_youtube_pipeline(
    pipeline_id: str,
    display_name: str,
    target_language: str,
    channel_id: str,
    privacy_status: str = "private",
    playlist_id: Optional[str] = None,
) -> PipelineConfig:
    """Create a YouTube pipeline configuration."""
    return PipelineConfig(
        pipeline_id=pipeline_id,
        pipeline_type=PipelineType.FULL_DUB,
        display_name=display_name,
        target_language=target_language,
        target=TargetConfig(
            target_type=TargetType.YOUTUBE,
            target_id=channel_id,
            display_name=f"YouTube: {display_name}",
            privacy_status=privacy_status,
            playlist_id=playlist_id,
            auto_publish=True,
        ),
    )


def create_local_pipeline(
    pipeline_id: str,
    display_name: str,
    target_language: str,
    output_path: str = "output",
) -> PipelineConfig:
    """Create a local output pipeline configuration."""
    return PipelineConfig(
        pipeline_id=pipeline_id,
        pipeline_type=PipelineType.FULL_DUB,
        display_name=display_name,
        target_language=target_language,
        target=TargetConfig(
            target_type=TargetType.LOCAL,
            target_id=output_path,
            display_name=f"Local: {display_name}",
        ),
    )
