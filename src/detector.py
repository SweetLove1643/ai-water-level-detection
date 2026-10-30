# Bước 4: AI (YOLO) + estimate_level()
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

class WaterDetector:
    def __init__(self, weights_path: str | Path | None = None, confidence: float = 0.6) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Ngưỡng confidence model lỗi")
        if weights_path is None or not weights_path.is_file():
            raise FileNotFoundError(f"Model path failed: {weights_path}")
        self._model = YOLO(str(weights_path))
        self._confidence = confidence

        names = self._model.names
        items = names.items() if isinstance(names, dict) else enumerate(names)
        self._water_class_ids = {
            int(class_id)
            for class_id, name in items
            if str(name).strip().casefold() == "water"
        }
        if not self._water_class_ids:
            raise ValueError(f"Model không có class 'water': {names}")

    def predict_water_mask(self, frame: np.ndarray) -> np.ndarray:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame phải là ảnh màu có shape (height, width, 3)")

        height, width = frame.shape[:2]
        water_mask = np.zeros((height, width), dtype=bool)

        results = self._model.predict(
            source=frame,
            conf=self._confidence,
            retina_masks=True,
            verbose=False,
        )

        if not results:
            return water_mask.astype(np.uint8) * 255

        result = results[0]
        if result.boxes is None or result.masks is None:
            return water_mask.astype(np.uint8) * 255

        class_ids = result.boxes.cls.int().cpu().numpy()
        masks = result.masks.data.cpu().numpy()

        if len(class_ids) != len(masks):
            raise RuntimeError(
                f"Số class và mask không khớp: {len(class_ids)} != {len(masks)}"
            )

        for class_id, predicted_mask in zip(class_ids, masks):
            if int(class_id) not in self._water_class_ids:
                continue

            if predicted_mask.shape != (height, width):
                predicted_mask = cv2.resize(
                    predicted_mask.astype(np.uint8),
                    (width, height),
                    interpolation=cv2.INTER_NEAREST,
                )

            water_mask |= predicted_mask > 0

        return water_mask.astype(np.uint8) * 255