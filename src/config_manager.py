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
        log.debug(cams)
        enabled = {
            c["code"]: CameraConfig(c["id"], c["code"], c["rtsp_url"])
            for c in cams
            if MODULE in (c.get("ai_modules") or [])
        }
        with self._lock:
            self._cameras =enabled
        log.info("camera bật %s: %s", MODULE, list(enabled))
        self._reconcile()

    def handle_zones(self, code: str, raw: bytes) -> None:
        zones = safe_json(raw).get("ai_zones") or []
        with self._lock:
            self._zones[code] = zones
        log.info("zones camera=%s: %d vùng", code, len(zones))
        self._reconcile(changed=code)

    def _reconcile(self, changed: str | None = None) -> None:
        with self._lock:
            want = {c for c in self._cameras if self._zones.get(c)}
            start = want - self._running
            stop = self._running - want
            update = ({changed} & want & self._running) if changed else set()
            self._running = want
            snap = {c: (self._cameras[c], self._zones[c]) for c in want}

        for c in stop:
            self.on_stop(c)
        for c in start:
            self.on_start(*snap[c])
        for c in update:
            self.on_update(c, snap[c][1])



