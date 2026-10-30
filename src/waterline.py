import json
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("waterline")

@dataclass(frozen=True)
class Mark:
    cm: float
    p1: tuple[float, float]
    p2: tuple[float, float]
    y_at_measure: float

@dataclass(frozen=True)
class Calibration:
    roi_points: tuple[tuple[float, float], ...]
    measure_x: float
    warn_cm: float
    marks: tuple[Mark, ...]

def _normalized_point(value: object, field: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field} must have form [x, y]")

    x, y = float(value[0]), float(value[1])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError(f"{field} must be within normalized coordinates 0..1")

    return x, y

def load_calibration(path: str | Path) -> Calibration:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    roi = data["roi"]
    roi_points = tuple(
        _normalized_point(point, "roi.points")
        for point in roi["points"]
    )
    if len(roi_points) < 3:
        raise ValueError("ROI must have at least 3 points")

    measure_x = float(roi["measure_x"])
    if not 0 <= measure_x <= 1:
        raise ValueError("roi.measure_x must be within normalized coordinates 0..1")

    marks = []
    for item in data["marks"]:
        cm = float(item["cm"])
        p1 = _normalized_point(item["p1"], f"mark {cm}.p1")
        p2 = _normalized_point(item["p2"], f"mark {cm}.p2")

        if p1[0] == p2[0]:
            raise ValueError(f"Mark {cm} has p1.x and p2.x that are the same")

        # Nội suy vị trí y của đường mốc tại measure_x.
        t = (measure_x - p1[0]) / (p2[0] - p1[0])
        if not 0 <= t <= 1:
            raise ValueError(
                f"measure_x does not lie on the mark {cm} cm"
            )

        y_at_measure = p1[1] + t * (p2[1] - p1[1]) # tính điểm trung tâm để làm mốc cần so sánh
        marks.append(Mark(cm, p1, p2, y_at_measure))

    marks.sort(key=lambda mark: mark.cm)
    if not marks:
        raise ValueError("Calibration must have at least one mark")

    for lower, higher in zip(marks, marks[1:]):
        if higher.y_at_measure >= lower.y_at_measure:
            raise ValueError(
                "Mốc cm cao hơn phải có tọa độ y nhỏ hơn trong ảnh"
            )

    calibration = Calibration(
        roi_points=roi_points,
        measure_x=measure_x,
        warn_cm=float(data["warn_cm"]),
        marks=tuple(marks),
    )
    log.info(
        "Loaded calibration: roi_points=%d marks=%d measure_x=%.3f",
        len(roi_points),
        len(marks),
        measure_x,
    )
    return calibration


def water_surface_y(
    water_mask: np.ndarray,
    calibration: Calibration,
    band_width_fraction: float = 0.01,
    min_run_px: int = 5,
    min_columns: int = 5,
) -> float | None:
    """Trả y mép nước dạng chuẩn hóa 0..1; None nếu không đủ tín hiệu."""
    if water_mask.ndim != 2:
        raise ValueError("water_mask must be a 2D mask")

    height, width = water_mask.shape
    if height == 0 or width == 0:
        raise ValueError("water_mask is empty")

    polygon = np.array(
        [
            [round(x * (width - 1)), round(y * (height - 1))]
            for x, y in calibration.roi_points
        ],
        dtype=np.int32,
    )
    roi_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(roi_mask, [polygon], 255)

    water_in_roi = (water_mask > 0) & (roi_mask > 0)

    center_x = round(calibration.measure_x * (width - 1))
    half_width = max(1, round(band_width_fraction * width / 2))
    x0 = max(0, center_x - half_width)
    x1 = min(width, center_x + half_width + 1)

    surface_rows = []
    for x in range(x0, x1):
        rows = np.flatnonzero(water_in_roi[:, x])
        if rows.size == 0:
            continue

        runs = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
        first_valid_run = next(
            (run for run in runs if len(run) >= min_run_px),
            None,
        )
        if first_valid_run is not None:
            surface_rows.append(int(first_valid_run[0]))

    if len(surface_rows) < min_columns:
        return None

    return float(np.median(surface_rows)) / (height - 1)


def level_band(
    surface_y: float | None,
    calibration: Calibration,
) -> float | None:
    """Trả mốc cm cao nhất mà mặt nước đã chạm/vượt qua."""
    if surface_y is None:
        return None

    reached = [
        mark.cm
        for mark in calibration.marks
        if surface_y <= mark.y_at_measure
    ]
    return max(reached) if reached else None


def is_warning(
    band_cm: float | None,
    active: bool,
    calibration: Calibration,
    margin_cm: float = 5.0,
) -> bool:
    if band_cm is None:
        return False

    threshold = (
        calibration.warn_cm - margin_cm
        if active
        else calibration.warn_cm
    )
    return band_cm >= threshold