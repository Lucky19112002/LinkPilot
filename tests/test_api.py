from config import Config
from api import ApiClient


def test_worker_identity_attached():
    client = ApiClient(Config(worker_id="W1", worker_name="Desk"))
    data = client.with_worker({"x": 1})
    assert data["worker_id"] == "W1"
    assert data["worker_name"] == "Desk"


def test_api_client_can_disable_tls_verification():
    client = ApiClient(Config(allow_insecure_https=True))
    assert client.session.verify is False
