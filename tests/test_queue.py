from queue_manager import QueueManager


def test_queue_retry_skip():
    q = QueueManager()
    q.load(["https://a.test"])
    q.skip("https://a.test")
    assert q.rows()[0][1] == "Skipped"
    q.retry("https://a.test")
    assert q.rows()[0] == ("https://a.test", "Waiting", 1)
