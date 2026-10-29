# Bước 5: hysteresis, cooldown, median
from dataclasses import dataclass

from src.waterline import Calibration, is_warning

@dataclass
class AlertState:
    active: bool = False
    last_report_at: float | None = None
    last_attempt_at: float | None = None

    def should_report(
        self,
        band_cm: float | None,
        calibration: Calibration,
        now: float,
        cooldown_s: float,
        margin_cm: float,
        retry_s: float = 5.0,
    ) -> bool:
        # Mất tín hiệu đo không đồng nghĩa mực nước đã hạ.
        if band_cm is None:
            return False

        warning = is_warning(
            band_cm=band_cm,
            active=self.active,
            calibration=calibration,
            margin_cm=margin_cm,
        )

        if not warning:
            # Kết thúc episode cảnh báo; lần vượt ngưỡng tiếp theo được gửi ngay.
            self.active = False
            self.last_report_at = None
            self.last_attempt_at = None
            return False

        self.active = True

        cooldown_elapsed = (
            self.last_report_at is None
            or now - self.last_report_at >= cooldown_s
        )
        retry_elapsed = (
            self.last_attempt_at is None
            or now - self.last_attempt_at >= retry_s
        )

        return cooldown_elapsed and retry_elapsed

    def record_attempt(self, now: float, success: bool) -> None:
        self.last_attempt_at = now
        if success:
            self.last_report_at = now