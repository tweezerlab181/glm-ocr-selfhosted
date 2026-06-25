from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def test_dockerignore_excludes_local_secrets_and_envs():
    dockerignore = REPO_ROOT / ".dockerignore"
    assert dockerignore.exists()

    patterns = {
        line.strip()
        for line in dockerignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert {
        ".env",
        "client.credentials.env",
        ".secrets/",
        ".git/",
        ".venv/",
        "gateway/.venv/",
    }.issubset(patterns)
