from pathlib import Path
from tempfile import TemporaryDirectory

from api import ApiClient
from config import Config, load_config, save_config
from worker import LinkPilotWorker


def test_config_roundtrip() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        save_config(Config(api_username="u", headless=True), path)
        loaded = load_config(path)
        assert loaded.api_username == "u"
        assert loaded.headless is True
        assert loaded.ollama_port == 11434
        assert loaded.max_ai_actions == 15
        assert loaded.profile["first_name"] == "Lucky"


def test_api_url_join() -> None:
    client = ApiClient(Config(api_base_url="https://example.com/base/"))
    assert client._url("auth.ashx") == "https://example.com/base/auth.ashx"


def test_worker_decision_and_detection() -> None:
    worker = LinkPilotWorker(Config())
    assert worker.parse_decision({"response": '{"action":{"type":"done"}}'})["action"]["type"] == "done"
    detected = worker.detect_result({"title": "", "url": "", "visible_text": "Enter verification code"})
    assert detected["status"] == "otp_required"


def test_password_not_in_config() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        path.write_text('{"api_username":"u","api_password":"secret","credential_id":"test"}', encoding="utf-8")
        loaded = load_config(path)
        text = path.read_text(encoding="utf-8")
        assert loaded.credential_id == "test"
        assert "secret" not in text
        assert "api_password" not in text


if __name__ == "__main__":
    test_config_roundtrip()
    test_api_url_join()
    test_worker_decision_and_detection()
    test_password_not_in_config()
    print("ok")
