import argparse
from pathlib import Path

import cv2
import numpy as np

from src.detector import WaterDetector
from src.waterline import load_calibration, level_band, water_surface_y


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        default="resources/data/img_org/frame_00000000.jpg",
    )
    parser.add_argument(
        "--output",
        default="runs/waterline_debug.jpg",
    )
    parser.add_argument(
        "--calibration",
        default="resources/config/water_marks.json",
    )
    args = parser.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(f"Không đọc được ảnh: {args.image}")

    calibration = load_calibration(args.calibration)
    detector = WaterDetector()
    water_mask = detector.predict_water_mask(frame)

    surface_y = water_surface_y(water_mask, calibration)
    band_cm = level_band(surface_y, calibration)

    height, width = frame.shape[:2]
    overlay = frame.copy()

    roi_points = np.array(
        [
            [round(x * (width - 1)), round(y * (height - 1))]
            for x, y in calibration.roi_points
        ],
        dtype=np.int32,
    )
    cv2.polylines(overlay, [roi_points], True, (0, 255, 0), 3)

    measure_x = round(calibration.measure_x * (width - 1))
    cv2.line(overlay, (measure_x, 0), (measure_x, height - 1), (0, 255, 255), 2)

    for mark in calibration.marks:
        p1 = (round(mark.p1[0] * (width - 1)), round(mark.p1[1] * (height - 1)))
        p2 = (round(mark.p2[0] * (width - 1)), round(mark.p2[1] * (height - 1)))
        cv2.line(overlay, p1, p2, (255, 200, 0), 2)
        cv2.putText(
            overlay,
            f"{mark.cm:g} cm",
            p1,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 200, 0),
            2,
        )

    if surface_y is not None:
        y_px = round(surface_y * (height - 1))
        cv2.line(overlay, (0, y_px), (width - 1, y_px), (0, 0, 255), 2)

    result_text = (
        f"surface_y={surface_y:.4f}, level_band={band_cm} cm"
        if surface_y is not None
        else "surface not detected"
    )
    cv2.putText(
        overlay,
        result_text,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), overlay):
        raise RuntimeError(f"Không lưu được ảnh debug: {output}")

    print(result_text)
    print(f"Đã lưu ảnh debug: {output}")


if __name__ == "__main__":
    main()