import os
import shutil
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def make_temp_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "scripts" / "gen_env.sh", root / "scripts" / "gen_env.sh")
    shutil.copy2(REPO_ROOT / ".env.example", root / ".env.example")
    return root


def run_gen_env(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/gen_env.sh", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_gateway_host_generates_server_env_and_client_credentials(tmp_path):
    root = make_temp_repo(tmp_path)

    result = run_gen_env(root, "--gateway-host", "132.77.40.253:8080")

    assert result.returncode == 0, result.stderr
    server = read_env(root / ".env")
    client = read_env(root / "client.credentials.env")
    assert server["API_KEY"]
    assert client == {
        "OCR_HOST": "132.77.40.253:8080",
        "OCR_API_KEY": server["API_KEY"],
    }
    assert mode(root / ".env") == 0o600
    assert mode(root / "client.credentials.env") == 0o600


def test_client_credentials_mode_reads_existing_server_env(tmp_path):
    root = make_temp_repo(tmp_path)
    (root / ".env").write_text("API_KEY=fixed-secret\nVLLM_URL=http://vllm:8080/v1\n", encoding="utf-8")

    result = run_gen_env(root, "--client-credentials", "--gateway-host", "132.77.40.253:8080")

    assert result.returncode == 0, result.stderr
    assert read_env(root / "client.credentials.env") == {
        "OCR_HOST": "132.77.40.253:8080",
        "OCR_API_KEY": "fixed-secret",
    }
    assert "fixed-secret" in (root / ".env").read_text(encoding="utf-8")


def test_client_credentials_refuses_overwrite_without_force(tmp_path):
    root = make_temp_repo(tmp_path)
    (root / ".env").write_text("API_KEY=fixed-secret\n", encoding="utf-8")
    client_path = root / "client.credentials.env"
    client_path.write_text("OCR_HOST=old\nOCR_API_KEY=old\n", encoding="utf-8")

    result = run_gen_env(root, "--client-credentials", "--gateway-host", "132.77.40.253:8080")

    assert result.returncode != 0
    assert "client.credentials.env already exists" in result.stderr
    assert client_path.read_text(encoding="utf-8") == "OCR_HOST=old\nOCR_API_KEY=old\n"


def test_client_credentials_force_overwrites_existing_file(tmp_path):
    root = make_temp_repo(tmp_path)
    (root / ".env").write_text("API_KEY=fixed-secret\n", encoding="utf-8")
    client_path = root / "client.credentials.env"
    client_path.write_text("OCR_HOST=old\nOCR_API_KEY=old\n", encoding="utf-8")

    result = run_gen_env(
        root,
        "--client-credentials",
        "--gateway-host",
        "132.77.40.253:8080",
        "--force",
    )

    assert result.returncode == 0, result.stderr
    assert read_env(client_path) == {
        "OCR_HOST": "132.77.40.253:8080",
        "OCR_API_KEY": "fixed-secret",
    }


def test_gateway_url_writes_ocr_url(tmp_path):
    root = make_temp_repo(tmp_path)
    (root / ".env").write_text("API_KEY=fixed-secret\n", encoding="utf-8")

    result = run_gen_env(root, "--client-credentials", "--gateway-host", "https://ocr.example.test/ocr")

    assert result.returncode == 0, result.stderr
    assert read_env(root / "client.credentials.env") == {
        "OCR_URL": "https://ocr.example.test/ocr",
        "OCR_API_KEY": "fixed-secret",
    }
