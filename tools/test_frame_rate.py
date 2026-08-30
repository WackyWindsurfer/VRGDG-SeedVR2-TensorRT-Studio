from __future__ import annotations

import math
import unittest

from seedvr_studio.media import FrameRateRequiredError, resolve_frame_rate


class ResolveFrameRateTests(unittest.TestCase):
    def test_detected_frame_rates_are_preserved(self) -> None:
        self.assertEqual(resolve_frame_rate(48.0), 48.0)
        self.assertEqual(resolve_frame_rate(29.97), 29.97)

    def test_override_is_used_when_detection_fails(self) -> None:
        self.assertEqual(resolve_frame_rate(0.0, 23.976), 23.976)
        self.assertEqual(resolve_frame_rate(math.nan, 60), 60.0)

    def test_invalid_frame_rates_require_user_input(self) -> None:
        for detected, override in ((0, 0), (math.nan, 0), (241, -1), (None, "bad")):
            with self.subTest(detected=detected, override=override):
                with self.assertRaises(FrameRateRequiredError):
                    resolve_frame_rate(detected, override)


if __name__ == "__main__":
    unittest.main()
