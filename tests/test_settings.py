import json
from dataclasses import asdict

from config import Config


def test_profile_export_excludes_secrets():
    data = asdict(Config())
    data.pop("profile", None)
    text = json.dumps(data)
    assert "api_password" not in text
    assert "password" not in text
