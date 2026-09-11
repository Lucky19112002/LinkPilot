from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueueItem:
    url: str
    status: str = "Waiting"
    attempts: int = 0


class QueueManager:
    def __init__(self):
        self.items: list[QueueItem] = []
        self.paused = False

    def load(self, urls: list[str]) -> None:
        existing = {item.url: item for item in self.items}
        self.items = [existing.get(url, QueueItem(url)) for url in urls]

    def skip(self, url: str) -> None:
        self._item(url).status = "Skipped"

    def retry(self, url: str) -> None:
        item = self._item(url)
        item.status = "Waiting"
        item.attempts += 1

    def mark(self, url: str, status: str) -> None:
        self._item(url).status = status

    def rows(self) -> list[tuple[str, str, int]]:
        return [(item.url, item.status, item.attempts) for item in self.items]

    def _item(self, url: str) -> QueueItem:
        for item in self.items:
            if item.url == url:
                return item
        item = QueueItem(url)
        self.items.append(item)
        return item
