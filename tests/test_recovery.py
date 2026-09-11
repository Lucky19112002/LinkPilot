from config import Config
from worker import LinkPilotWorker


def test_loop_detection_repeated_action():
    worker = LinkPilotWorker(Config())
    for _ in range(3):
        worker.remember_action({"type": "vision_click", "x": 1, "y": 2}, "same")
    assert worker.detect_loop() == "actions"
