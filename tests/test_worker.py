from config import Config
from worker import LinkPilotWorker


def test_worker_prepares_hybrid_actions():
    worker = LinkPilotWorker(Config())
    assert worker.prepare_action({"type": "click"})["type"] == "dom_click"
    assert worker.prepare_action({"type": "vision_click", "x": 1, "y": 2})["type"] == "vision_click"
