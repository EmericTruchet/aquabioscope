import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from aquabioscope import feedback


class FeedbackTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, {feedback.DISABLE_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _wait_for(self, condition) -> None:
        deadline = time.time() + 5
        while not condition() and time.time() < deadline:
            time.sleep(0.01)

    def test_sent_request_leaves_the_queue(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.json"
            sent = []
            feedback.report_unlisted_species("  Doris   à pois  ", "mer-rouge", path=path,
                                             send=lambda r: sent.append(r) or True)
            self._wait_for(lambda: sent)
            self._wait_for(lambda: json.loads(path.read_text(encoding="utf-8")) == [])
            self.assertEqual(sent, [{"nom": "Doris à pois", "zone": "mer-rouge"}])

    def test_offline_requests_wait_for_next_flush(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.json"
            feedback.report_unlisted_species("Espèce A", None, path=path, send=lambda r: False)
            feedback.report_unlisted_species("Espèce B", "atlantique", path=path, send=lambda r: False)
            self._wait_for(lambda: len(json.loads(path.read_text(encoding="utf-8"))) == 2)
            time.sleep(0.1)  # laisse finir les envois en echec
            sent = []
            self.assertEqual(feedback.flush(path, send=lambda r: sent.append(r) or True), 2)
            self.assertEqual([r["nom"] for r in sent], ["Espèce A", "Espèce B"])
            self.assertEqual(sent[0]["zone"], "autre")
            self.assertEqual(feedback.flush(path, send=lambda r: True), 0)

    def test_disabled_by_environment(self) -> None:
        with TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {feedback.DISABLE_ENV: "1"}):
            path = Path(tmp) / "file.json"
            feedback.report_unlisted_species("Espèce A", None, path=path, send=lambda r: True)
            self.assertFalse(path.exists())

    def test_corrupt_queue_is_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.json"
            path.write_text("{{{", encoding="utf-8")
            self.assertEqual(feedback.flush(path, send=lambda r: True), 0)


if __name__ == "__main__":
    unittest.main()
