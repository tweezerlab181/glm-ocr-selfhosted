import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


RUNNER = Path(__file__).parents[1] / "skills" / "ocr" / "scripts" / "run_ocr.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("ocr_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class OcrSkillRunnerTests(unittest.TestCase):
    def test_default_output_path_uses_source_stem(self):
        runner = load_runner()

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "paper.scan.pdf"
            source.write_bytes(b"%PDF-1.7")

            self.assertEqual(
                runner.default_output_path(source),
                Path(tmp) / "paper.scan.md",
            )

    def test_endpoint_from_defaults_port_for_server_lan_ip(self):
        runner = load_runner()

        self.assertEqual(
            runner.endpoint_from("192.168.1.20"),
            "http://192.168.1.20:8080/ocr",
        )

    def test_posts_file_and_writes_markdown_next_to_source(self):
        runner = load_runner()

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "scan.png"
            source.write_bytes(b"image bytes")
            body = json.dumps({"markdown": "# OCR\n\ntext", "pages": 1}).encode()

            with mock.patch.object(runner.urllib.request, "urlopen", return_value=FakeResponse(200, body)) as urlopen:
                output = runner.run_ocr(source, host="ocr.local:8080", api_key="secret")

            self.assertEqual(output, Path(tmp) / "scan.md")
            self.assertEqual(output.read_text(encoding="utf-8"), "# OCR\n\ntext\n")
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, "http://ocr.local:8080/ocr")
            self.assertEqual(request.headers["X-api-key"], "secret")
            content_type = request.headers["Content-type"]
            self.assertIn("multipart/form-data; boundary=", content_type)
            self.assertIn(b'name="file"; filename="scan.png"', request.data)

    def test_uses_server_lan_ip_env_when_ocr_host_is_unset(self):
        runner = load_runner()

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "scan.png"
            source.write_bytes(b"image bytes")
            body = json.dumps({"markdown": "ok", "pages": 1}).encode()

            with mock.patch.dict(runner.os.environ, {"API_KEY": "secret", "SERVER_LAN_IP": "10.0.0.5"}, clear=True):
                with mock.patch.object(runner.urllib.request, "urlopen", return_value=FakeResponse(200, body)) as urlopen:
                    runner.run_ocr(source)

            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, "http://10.0.0.5:8080/ocr")


if __name__ == "__main__":
    unittest.main()
