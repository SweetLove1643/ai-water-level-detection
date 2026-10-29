# Bước 2: camera + zone, bật/tắt worker
import json
import logging
import threading
from dataclasses import dataclass

from src.config import MODULE

log = logging.getLogger("config_manager")

def safe_json(raw: bytes) -> dict:
    if not raw or not raw.strip():
        return {}

    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        log.warning("payload không phải JSON, bỏ qua")
        return {}
@dataclass
class CameraConfig:
    id: str
    code: str
    rtsp_url: str
    
class ConfigManager:

    def __init__(self, on_start, on_stop, on_update):
        self._lock = threading.Lock()
        self._cameras: dict[str, CameraConfig] = {}
        self._zones: dict[str, list] = {}
        self._running: set[str] = set()
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_update = on_update

    def handle_cameras(self, raw: bytes) -> None:
        cams = safe_json(raw=raw).get("cameras") or []
        enabled = {
            c["code"]: CameraConfig(c["id"], c["code"], c["rtsp_url"])
            for c in cams
            if MODULE in (c.get("ai_modules") or [])
        }
        with self._lock:
            self._cameras =enabled
        log.info("camera bật %s: %s", MODULE, list(enabled))
        self._reconcile()

    def handle_zones(self, topic_code: str, raw: bytes) -> None:
        payload = safe_json(raw)
        zones = payload.get("ai_zones", [])

        if not isinstance(zones, list):
            log.warning("ai_zones không phải list; topic camera=%s", topic_code)
            return

        payload_code = payload.get("camera_code")
        payload_id = payload.get("camera_id")

        with self._lock:
            camera_by_id = next(
                (
                    camera
                    for camera in self._cameras.values()
                    if payload_id and camera.id == payload_id
                ),
                None,
            )
            if camera_by_id is not None:
                code = camera_by_id.code
            elif isinstance(payload_code, str) and payload_code.strip():
                code = payload_code.strip()
            else:
                code = topic_code
            if code != topic_code:
                log.warning(
                    "Camera code topic/payload khác nhau: topic=%s payload=%s; dùng=%s",
                    topic_code,
                    payload_code,
                    code,
                )
            log.info(
                "ZONE mapping topic_code=%s payload_code=%s camera_id_present=%s "
                "resolved_code=%s zones=%d known_cameras=%s",
                topic_code,
                payload_code,
                bool(payload_id),
                code,
                len(zones),
                list(self._cameras),
            )

            self._zones[code] = zones

        log.info("zones camera=%s: %d vùng", code, len(zones))
        self._reconcile(changed=code)

    def _reconcile(self, changed: str | None = None) -> None:
        with self._lock:
            # want = {c for c in self._cameras if self._zones.get(c)}
            want = set(self._cameras)

            start = want - self._running
            stop = self._running - want
            update = ({changed} & want & self._running) if changed else set()
            self._running = want

            snap = {
                code: (self._cameras[code], self._zones.get(code, []))
                for code in want
            }

        for c in stop:
            self.on_stop(c)
        for c in start:
            self.on_start(*snap[c])
        for c in update:
            self.on_update(c, snap[c][1])

        log.info(
            "RECONCILE cameras=%s zones=%s start=%s stop=%s update=%s",
            list(self._cameras),
            list(self._zones),
            sorted(start),
            sorted(stop),
            sorted(update),
        )



