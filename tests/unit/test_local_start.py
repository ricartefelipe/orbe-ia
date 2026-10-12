"""The published start path does not require a local env file."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_start_script_only_runs_compose() -> None:
    script = (ROOT / "scripts" / "start.sh").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "docker compose up --build" in script
    assert "./scripts/start.sh" in readme
    assert "docker compose up --build" in readme
    assert ".env" not in script
    assert ".env" not in readme
    assert "cp " not in script
    assert "python -m orbe" in entrypoint
