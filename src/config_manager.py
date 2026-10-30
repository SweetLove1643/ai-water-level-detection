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

    def __init__(self, on_start, on_stop):
        self._lock = threading.Lock()
        self._cameras: dict[str, CameraConfig] = {}
        self._running: set[str] = set()
        self.on_start = on_start
        self.on_stop = on_stop

    def handle_cameras(self, raw: bytes) -> None:
        cams = safe_json(raw=raw).get("cameras") or []
        enabled = {
            c["code"]: CameraConfig(c["id"], c["code"], c["rtsp_url"])
            for c in cams
            if MODULE in (c.get("ai_modules") or [])
        }
        with self._lock:
            self._cameras =enabled
        log.info("Camera bật module: %s: %s", MODULE, list(enabled))
        self._reconcile()

    def _reconcile(self) -> None:
        with self._lock:
            want = set(self._cameras)

            start = want - self._running
            stop = self._running - want   

            snap = {
                code: (self._cameras[code])
                for code in want
            }

        for c in stop:
            self.on_stop(c)
        for c in start:
            self.on_start(snap[c])
        self._running = want

        log.info(
            "RECONCILE cameras=%s start=%s stop=%s",
            list(self._cameras),
            sorted(start),
            sorted(stop),
        )



