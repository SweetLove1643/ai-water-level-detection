# Bước 3: 1 camera = 1 thread, đọc RTSP
import logging
import threading
from collections.abc import Sequence

import cv2

from src.config_manager import CameraConfig

log = logging.getLogger("worker")

OPEN_TIMEOUT_MS = 5_000
READ_TIMEOUT_MS = 5_000
RECONNECT_DELAY_S = 3

class CameraWorker:
    def __init__(self, camera: CameraConfig, zones: Sequence[dict[str, object]]) -> None:
        self.camera = camera
        self._zones = list(zones)
        self._zones_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError(f"Woker cho camera {self.camera.code} đã được start")

        self._thread = threading.Thread(
            target=self._run,
            name=f"camera-{self.camera.code}",
            daemon=True
        )
        self._thread.start()

    def update_zones(self, zones: Sequence[dict[str, object]]) -> None:
        with self._zones_lock:
            self._zones = list(zones)
        log.info("Đã cập nhật cung camera=%s count=%d", self.camera.code, len(zones))

    def zones_snapshot(self) -> list[dict[str, object]]:
        with self._zones_lock:
            return list(self._zones)

    def stop(self, timeout: float = 7) -> None:
        self._stop_event.set()

        if self._thread is None:
            return

        self._thread.join(timeout=timeout)

        if self._thread.is_alive():
            log.warning("Worker camera=%s chưa dừng sau %.1f giây", self.camera.code, timeout)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            capture = None

            try:
                capture = cv2.VideoCapture(
                    self.camera.rtsp_url,
                    cv2.CAP_FFMPEG,
                    [
                        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                        OPEN_TIMEOUT_MS,
                        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                        READ_TIMEOUT_MS,
                    ],
                )

                if not capture.isOpened():
                    log.warning(f"Không mở được RTSP camera=%s, {self.camera.rtsp_url}", self.camera.code)
                else:
                    log.info("Đã mở RTSP camera=%s", self.camera.code)

                    while not self._stop_event.is_set():
                        ok, frame = capture.read()

                        if not ok or frame is None:
                            log.warning("Mất frame RTSP camera=%s; sẽ thử kết nối lại", self.camera.code)
                            break

                        # Bước sau sẽ chuyển frame và zones_snapshot() vào detector.
                
            except cv2.error:
                log.exception("OpenCV gặp lỗi với camera=%s", self.camera.code)

            finally:
                if capture is not None:
                    capture.release()

            if not self._stop_event.is_set():
                self._stop_event.wait(RECONNECT_DELAY_S)

        log.info("Worker camera=%s đã dừng", self.camera.code)