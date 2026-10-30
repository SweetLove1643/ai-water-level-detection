# Bước 3: 1 camera = 1 thread, đọc RTSP
import logging
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import cv2

from src.detector import WaterDetector
from src.waterline import load_calibration, water_surface_y, level_band

import src.config as cf
from src.state import AlertState

from src.config_manager import CameraConfig

log = logging.getLogger("worker")

OPEN_TIMEOUT_MS = 5_000
READ_TIMEOUT_MS = 5_000
RECONNECT_DELAY_S = 3

class CameraWorker:
    def __init__(
        self,
        camera: CameraConfig,
        publish_alert: Callable[[float, bytes], bool],
    ) -> None:
        self.camera = camera
        self._publish_alert = publish_alert
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError(f"Woker for camera {self.camera.code} started")

        self._thread = threading.Thread(
            target=self._run,
            name=f"camera-{self.camera.code}",
            daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 7) -> None:
        self._stop_event.set()

        if self._thread is None:
            return

        self._thread.join(timeout=timeout)

        if self._thread.is_alive():
            log.warning("Worker camera=%s haven't stopped yet %.1f second", self.camera.code, timeout)

    def _run(self) -> None:
        alert_state = AlertState()
        last_measurement_log = 0.0

        # Khởi tạo model
        water_marks_path = Path(cf.WATER_MARKS_CONFIG_PATH)
        calibration = load_calibration(water_marks_path)

        weight_path = Path(cf.WEIGHT_WATER_MODEL_SEGMENT_PATH)
        confidence = float(cf.WATER_MODEL_SEGMENT_CONFIDENCE)

        detector = WaterDetector(weights_path=weight_path, confidence=confidence)

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
                    log.warning("Cannot open RTSP rtsp=%s camera=%s", self.camera.rtsp_url, self.camera.code)
                else:
                    log.info("Opened RTSP camera=%s", self.camera.code)

                    while not self._stop_event.is_set():
                        ok, frame = capture.read()

                        if not ok or frame is None:
                            log.warning(
                                "Cannot read frame: camera=%s, ok=%s, frame_is_none=%s",
                                self.camera.code,
                                ok,
                                frame is None,
                            )
                            break

                        water_mask = detector.predict_water_mask(frame)
                        surface_y = water_surface_y(water_mask, calibration)
                        level_cm = level_band(surface_y, calibration)

                        now = time.monotonic()
                        if now - last_measurement_log >= 10.0:
                            log.info(
                                "Water measurement camera=%s surface_y=%s level_band_cm=%s",
                                self.camera.code,
                                None if surface_y is None else round(surface_y, 4),
                                level_cm,
                            )
                            last_measurement_log = now

                        if alert_state.should_report(
                            band_cm=level_cm,
                            calibration=calibration,
                            now=now,
                            cooldown_s=cf.COOLDOWN_S,
                            margin_cm=cf.MARGIN_CM,
                        ):
                            encoded_ok, encoded = cv2.imencode(".jpg", frame)

                            if not encoded_ok:
                                log.error("Not able to encode snapshot camera=%s", self.camera.code)
                                success = False
                            else:
                                try:
                                    success = self._publish_alert(level_cm, encoded.tobytes())
                                except Exception:
                                    log.exception("Send alert failed for camera=%s", self.camera.code)
                                    success = False

                            alert_state.record_attempt(
                                now=time.monotonic(),
                                success=success,
                            )
                
            except Exception:
                log.exception("OpenCV failed for camera=%s", self.camera.code)

            finally:
                if capture is not None:
                    capture.release()

            if not self._stop_event.is_set():
                self._stop_event.wait(RECONNECT_DELAY_S)

        log.info("Worker camera=%s has stopped", self.camera.code)