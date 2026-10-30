# Bước 3: 1 camera = 1 thread, đọc RTSP
import logging
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import cv2

from src.detector import WaterDetector
from src.waterline import (
    Calibration,
    load_calibration,
    water_surface_y,
    level_band,
)

import src.config as cf
from src.state import AlertState

from src.config_manager import CameraConfig

log = logging.getLogger("worker")

OPEN_TIMEOUT_MS = 5_000
READ_TIMEOUT_MS = 5_000
RECONNECT_DELAY_S = 3

def calibration_overlays(
    calibration: Calibration,
    padding: float = 0.001,
) -> list[dict[str, object]]:
    xs = [x for x, _ in calibration.roi_points]
    ys = [y for _, y in calibration.roi_points]

    overlays: list[dict[str, object]] = [{
        "id": "measurement-roi",
        "class": "MEASUREMENT_ROI",
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
    }]

    for mark in calibration.marks:
        x1, y1 = mark.p1
        x2, y2 = mark.p2
        overlays.append({
            "id": f"mark-{mark.cm:g}cm",
            "class": f"MARK_{mark.cm:g}CM",
            "bbox": [
                max(0.0, min(x1, x2) - padding),
                max(0.0, min(y1, y2) - padding),
                min(1.0, max(x1, x2) + padding),
                min(1.0, max(y1, y2) + padding),
            ],
        })

    return overlays

class CameraWorker:
    def __init__(
        self,
        camera: CameraConfig,
        publish_alert: Callable[[float, bytes], bool],
        publish_bbox: Callable[[list[dict[str, object]], str], bool],
    ) -> None:
        self.camera = camera
        self._publish_alert = publish_alert
        self._publish_bbox = publish_bbox
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
        last_bbox_publish = 0.0

        # Khởi tạo model
        water_marks_path = Path(cf.WATER_MARKS_CONFIG_PATH)
        calibration = load_calibration(water_marks_path)
        calibration_detections = calibration_overlays(calibration)

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

                        water_mask, detections = detector.predict_with_detections(frame)
                        surface_y = water_surface_y(water_mask, calibration)
                        level_cm = level_band(surface_y, calibration)

                        now = time.monotonic()
                        if now - last_bbox_publish >= 0.005:
                            hud_text = (
                                f"Mực nước: {level_cm:g} cm"
                                if level_cm is not None
                                else "Mực nước: chưa xác định"
                            )
                            self._publish_bbox(
                                [*detections, *calibration_detections],
                                hud_text,
                            )
                            last_bbox_publish = now
                        
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

