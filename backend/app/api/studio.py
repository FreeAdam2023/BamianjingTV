"""Virtual Studio API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.studio import (
    CharacterRequest,
    LightingRequest,
    PrivacyRequest,
    SceneRequest,
    ScreenContentRequest,
    StudioCommandResponse,
    StudioPresets,
    StudioState,
    WeatherRequest,
)
from app.services.studio_manager import StudioManager

router = APIRouter(prefix="/studio", tags=["studio"])

_studio_manager: Optional[StudioManager] = None

UE_OFFLINE_MSG = "UE5 unreachable — command not applied"


def set_studio_manager(manager: StudioManager) -> None:
    """Set the studio manager instance."""
    global _studio_manager
    _studio_manager = manager


def _get_manager() -> StudioManager:
    if _studio_manager is None:
        raise HTTPException(status_code=503, detail="Studio manager not initialized")
    return _studio_manager


@router.get("/status", response_model=StudioState)
async def get_status():
    """Get current virtual studio state."""
    return _get_manager().get_state()


@router.get("/presets", response_model=StudioPresets)
async def get_presets():
    """Get available presets for all categories."""
    return _get_manager().get_presets()


@router.post("/scene", response_model=StudioCommandResponse)
async def set_scene(request: SceneRequest):
    """Switch scene preset."""
    manager = _get_manager()
    ok = await manager.set_scene(request)
    return StudioCommandResponse(
        success=ok,
        message=f"Scene set to {request.preset.value}" if ok else UE_OFFLINE_MSG,
        state=manager.get_state(),
    )


@router.post("/weather", response_model=StudioCommandResponse)
async def set_weather(request: WeatherRequest):
    """Change weather and time of day."""
    manager = _get_manager()
    ok = await manager.set_weather(request)
    return StudioCommandResponse(
        success=ok,
        message=f"Weather: {request.type.value}, time: {request.time_of_day:.1f}" if ok else UE_OFFLINE_MSG,
        state=manager.get_state(),
    )


@router.post("/privacy", response_model=StudioCommandResponse)
async def set_privacy(request: PrivacyRequest):
    """Set privacy blur level."""
    manager = _get_manager()
    ok = await manager.set_privacy(request)
    return StudioCommandResponse(
        success=ok,
        message=f"Privacy level: {request.level:.0%}" if ok else UE_OFFLINE_MSG,
        state=manager.get_state(),
    )


@router.post("/lighting", response_model=StudioCommandResponse)
async def set_lighting(request: LightingRequest):
    """Adjust studio lighting."""
    manager = _get_manager()
    ok = await manager.set_lighting(request)
    return StudioCommandResponse(
        success=ok,
        message="Lighting updated" if ok else UE_OFFLINE_MSG,
        state=manager.get_state(),
    )


@router.post("/character", response_model=StudioCommandResponse)
async def set_character(request: CharacterRequest):
    """Change character action and/or expression."""
    manager = _get_manager()
    ok = await manager.set_character(request)
    return StudioCommandResponse(
        success=ok,
        message="Character updated" if ok else UE_OFFLINE_MSG,
        state=manager.get_state(),
    )


@router.post("/screen", response_model=StudioCommandResponse)
async def set_screen_content(request: ScreenContentRequest):
    """Change monitor screen content source."""
    manager = _get_manager()
    ok = await manager.set_screen_content(request)
    return StudioCommandResponse(
        success=ok,
        message=f"Screen content: {request.content_type.value}" if ok else UE_OFFLINE_MSG,
        state=manager.get_state(),
    )
