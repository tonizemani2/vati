from __future__ import annotations

import unittest
from unittest import mock

from engine import disk_guard


class DiskGuardTests(unittest.TestCase):
    def test_default_floor_is_conservative_for_laptop_data_runs(self) -> None:
        self.assertGreaterEqual(disk_guard.DEFAULT_MIN_FREE_GB, 85)

    def test_assert_safe_allows_healthy_disk(self) -> None:
        with mock.patch("shutil.disk_usage", return_value=(100 * disk_guard.GIB, 60 * disk_guard.GIB, 40 * disk_guard.GIB)):
            stats = disk_guard.assert_safe(".", min_free_gb=25, max_used_pct=92)

        self.assertAlmostEqual(stats["free_gb"], 40)
        self.assertAlmostEqual(stats["used_pct"], 60)

    def test_assert_safe_rejects_low_free_space(self) -> None:
        with mock.patch("shutil.disk_usage", return_value=(100 * disk_guard.GIB, 95 * disk_guard.GIB, 5 * disk_guard.GIB)):
            with self.assertRaises(disk_guard.DiskSpaceError):
                disk_guard.assert_safe(".", min_free_gb=25, max_used_pct=92, label="collector")

    def test_assert_safe_override_allows_low_disk(self) -> None:
        with mock.patch("shutil.disk_usage", return_value=(100 * disk_guard.GIB, 95 * disk_guard.GIB, 5 * disk_guard.GIB)):
            stats = disk_guard.assert_safe(".", min_free_gb=25, max_used_pct=92, allow_low_disk=True)

        self.assertAlmostEqual(stats["free_gb"], 5)


if __name__ == "__main__":
    unittest.main()
