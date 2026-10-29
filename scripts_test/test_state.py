from dataclasses import replace
import unittest
from pathlib import Path

from src.state import AlertState
from src.waterline import load_calibration


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_PATH = (
    PROJECT_ROOT / "resources" / "config" / "water_marks.json"
)


class AlertStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calibration = replace(
            load_calibration(CALIBRATION_PATH),
            warn_cm=50.0,
        )

    def should_report(
        self,
        state: AlertState,
        band_cm: float | None,
        now: float,
    ) -> bool:
        return state.should_report(
            band_cm=band_cm,
            calibration=self.calibration,
            now=now,
            cooldown_s=10.0,
            margin_cm=5.0,
            retry_s=5.0,
        )

    def test_reports_immediately_then_after_cooldown(self) -> None:
        state = AlertState()

        self.assertTrue(self.should_report(state, band_cm=50, now=0))
        state.record_attempt(now=0, success=True)

        self.assertFalse(self.should_report(state, band_cm=50, now=9))
        self.assertTrue(self.should_report(state, band_cm=50, now=10))

    def test_failed_attempt_can_retry_after_retry_delay(self) -> None:
        state = AlertState()

        self.assertTrue(self.should_report(state, band_cm=50, now=0))
        state.record_attempt(now=0, success=False)

        self.assertFalse(self.should_report(state, band_cm=50, now=4))
        self.assertTrue(self.should_report(state, band_cm=50, now=5))

    def test_missing_measurement_does_not_clear_active_alert(self) -> None:
        state = AlertState()

        self.assertTrue(self.should_report(state, band_cm=50, now=0))
        state.record_attempt(now=0, success=True)

        self.assertFalse(self.should_report(state, band_cm=None, now=2))
        self.assertTrue(state.active)

    def test_water_drop_resets_alert_and_next_episode_reports_immediately(self) -> None:
        state = AlertState()

        self.assertTrue(self.should_report(state, band_cm=50, now=0))
        state.record_attempt(now=0, success=True)

        # 20 cm thấp hơn ngưỡng thoát 45 cm (50 - margin 5).
        self.assertFalse(self.should_report(state, band_cm=20, now=2))
        self.assertFalse(state.active)

        self.assertTrue(self.should_report(state, band_cm=50, now=3))


if __name__ == "__main__":
    unittest.main()