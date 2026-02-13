"""Studio Manager — state management + UE5 HTTP control forwarding."""

import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.models.studio import (
    CharacterAction,
    CharacterExpression,
    CharacterRequest,
    LightingRequest,
    PrivacyRequest,
    ScenePreset,
    SceneRequest,
    StudioPresets,
    StudioState,
    WeatherRequest,
    WeatherType,
)

logger = logging.getLogger(__name__)


class StudioManager:
    """Manages virtual studio state and forwards commands to UE5."""

    def __init__(
        self,
        ue_base_url: str = "http://192.168.1.200:30010",
        pixel_streaming_url: str = "http://192.168.1.200:80",
        state_file: Optional[Path] = None,
    ):
        self._ue_base_url = ue_base_url
        self._pixel_streaming_url = pixel_streaming_url
        self._state_file = state_file
        self._state = StudioState(pixel_streaming_url=pixel_streaming_url)
        self._client: Optional[httpx.AsyncClient] = None
        self._load_state()

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if self._state_file and self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._state = StudioState(**data)
                self._state.pixel_streaming_url = self._pixel_streaming_url
                logger.info(f"Loaded studio state from {self._state_file}")
            except Exception as e:
                logger.warning(f"Failed to load studio state: {e}")

    def _save_state(self) -> None:
        """Persist current state to disk."""
        if self._state_file:
            try:
                self._state_file.parent.mkdir(parents=True, exist_ok=True)
                self._state_file.write_text(
                    json.dumps(self._state.model_dump(mode="json"), indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.warning(f"Failed to save studio state: {e}")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None and self._client.is_closed:
            self._client = None
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._ue_base_url,
                timeout=5.0,
            )
        return self._client

    async def _forward_to_ue(self, endpoint: str, payload: dict) -> bool:
        """Forward a command to the UE5 HTTP server. Returns True on success."""
        try:
            client = await self._get_client()
            resp = await client.post(endpoint, json=payload)
            if resp.status_code == 200:
                logger.info(f"UE5 command OK: {endpoint} {payload}")
                return True
            logger.warning(f"UE5 command failed ({resp.status_code}): {endpoint}")
            return False
        except httpx.ConnectError:
            logger.warning(f"UE5 not reachable at {self._ue_base_url}")
            return False
        except Exception as e:
            logger.error(f"UE5 command error: {e}")
            return False

    # ---- State accessors ----

    def get_state(self) -> StudioState:
        return self._state.model_copy()

    def get_presets(self) -> StudioPresets:
        return StudioPresets(
            scenes=[e.value for e in ScenePreset],
            weather_types=[e.value for e in WeatherType],
            character_actions=[e.value for e in CharacterAction],
            character_expressions=[e.value for e in CharacterExpression],
            lighting_presets=["interview", "dramatic", "soft", "natural"],
        )

    # ---- Control commands ----
    # Only update local state when UE5 confirms success.

    async def set_scene(self, req: SceneRequest) -> bool:
        ok = await self._forward_to_ue("/set_scene", {"preset": req.preset.value})
        if ok:
            self._state.scene = req.preset
            self._save_state()
        self._state.ue_connected = ok
        return ok

    async def set_weather(self, req: WeatherRequest) -> bool:
        ok = await self._forward_to_ue(
            "/set_weather",
            {"type": req.type.value, "time_of_day": req.time_of_day},
        )
        if ok:
            self._state.weather = req.type
            self._state.time_of_day = req.time_of_day
            self._save_state()
        self._state.ue_connected = ok
        return ok

    async def set_privacy(self, req: PrivacyRequest) -> bool:
        ok = await self._forward_to_ue("/set_privacy", {"level": req.level})
        if ok:
            self._state.privacy_level = req.level
            self._save_state()
        self._state.ue_connected = ok
        return ok

    async def set_lighting(self, req: LightingRequest) -> bool:
        payload: dict = {
            "key": req.key,
            "fill": req.fill,
            "back": req.back,
            "temperature": req.temperature,
        }
        if req.preset:
            payload["preset"] = req.preset.value
        ok = await self._forward_to_ue("/set_lighting", payload)
        if ok:
            self._state.lighting_key = req.key
            self._state.lighting_fill = req.fill
            self._state.lighting_back = req.back
            self._state.lighting_temperature = req.temperature
            self._save_state()
        self._state.ue_connected = ok
        return ok

    async def set_character(self, req: CharacterRequest) -> bool:
        payload: dict = {}
        if req.action:
            payload["action"] = req.action.value
        if req.expression:
            payload["expression"] = req.expression.value
        if not payload:
            return True
        ok = await self._forward_to_ue("/set_character", payload)
        if ok:
            if req.action:
                self._state.character_action = req.action
            if req.expression:
                self._state.character_expression = req.expression
            self._save_state()
        self._state.ue_connected = ok
        return ok

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
