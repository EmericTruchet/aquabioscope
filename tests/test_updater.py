import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from aquabioscope import updater
from aquabioscope.updater import InstallKind, install_kind, is_newer, parse_version

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_notes  # noqa: E402


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

    def test_update_carries_release_notes(self) -> None:
        release = {
            "tag_name": "v99.0.0", "html_url": "https://exemple/release", "body": "- Nouveauté **A**\r\n",
            "assets": [{"name": updater.INSTALLER_ASSET, "browser_download_url": "https://exemple/setup.exe"}],
        }
        response = io.BytesIO(json.dumps(release).encode())
        with mock.patch.object(updater.urllib.request, "urlopen", return_value=response), \
                mock.patch.dict("os.environ", {updater.DISABLE_ENV: ""}):
            info = updater.check_for_update()
        self.assertEqual(info.version, "99.0.0")
        self.assertEqual(info.notes, "- Nouveauté **A**")
        self.assertEqual(info.installer_url, "https://exemple/setup.exe")


class ReleaseNotesTest(unittest.TestCase):
    CHANGELOG = "# Titre\n\nintro\n\n## 1.1.0\n\n- deux\n\n## 1.0.0\n\n- un\n"

    def test_extracts_only_the_requested_version(self) -> None:
        self.assertEqual(release_notes.section("v1.1.0", self.CHANGELOG), "- deux")
        self.assertEqual(release_notes.section("1.0.0", self.CHANGELOG), "- un")
        self.assertIsNone(release_notes.section("2.0.0", self.CHANGELOG))

    def test_current_version_has_release_notes(self) -> None:
        # une version ne doit pas partir sans note : le build du tag echouerait
        text = release_notes.CHANGELOG.read_text(encoding="utf-8")
        self.assertTrue(release_notes.section(updater.__version__, text))


if __name__ == "__main__":
    unittest.main()
