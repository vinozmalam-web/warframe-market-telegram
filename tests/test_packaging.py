from pathlib import Path


def test_compose_uses_named_volume_for_sqlite_state():
    compose = Path("docker-compose.yml").read_text()

    assert "market-message-data:/app/data" in compose
    assert "./data:/app/data" not in compose
    assert "\nvolumes:\n  market-message-data:" in compose
