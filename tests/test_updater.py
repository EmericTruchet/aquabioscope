import unittest

from aquabioscope.updater import InstallKind, install_kind, is_newer, parse_version


class UpdaterTest(unittest.TestCase):
    def test_parse_version_ignores_prefix_and_suffix(self) -> None:
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("0.10.0-beta"), (0, 10, 0))

    def test_is_newer_compares_numerically(self) -> None:
        self.assertTrue(is_newer("v0.10.0", "0.9.5"))
        self.assertFalse(is_newer("v0.2.0", "0.2.0"))
        self.assertFalse(is_newer("v0.1.9", "0.2.0"))

    def test_running_from_sources_is_not_auto_updatable(self) -> None:
        self.assertIs(install_kind(), InstallKind.OTHER)


if __name__ == "__main__":
    unittest.main()
