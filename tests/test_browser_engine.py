from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from browser import BrowserEngine
from config import Config


ROOT = Path(__file__).parent / "websites"


def page_url(name: str) -> str:
    return (ROOT / name).resolve().as_uri()


def find(elements: list[dict], text: str) -> dict:
    needle = text.lower()
    for element in elements:
        hay = " ".join(str(element.get(key, "")) for key in ("text", "label", "placeholder", "name")).lower()
        if needle in hay:
            return element
    raise AssertionError(f"missing element {text}")


def test_registration_form() -> None:
    browser = BrowserEngine(Config(headless=True, human_typing=False))
    try:
        browser.launch()
        browser.goto(page_url("registration.html"))
        snapshot, _ = browser.page_snapshot([])
        first = find(snapshot["interactive_elements"], "First name")
        done, result = browser.execute_action({"type": "type", "element_id": first["id"], "text": "Lucky"}, snapshot["interactive_elements"])
        assert not done
        assert result == "ok"
        assert browser.page.locator('[name="first_name"]').input_value() == "Lucky"
    finally:
        browser.close()


def test_select_check_and_new_tab() -> None:
    browser = BrowserEngine(Config(headless=True, human_typing=False))
    try:
        browser.launch()
        browser.goto(page_url("dropdown.html"))
        snapshot, _ = browser.page_snapshot([])
        country = find(snapshot["interactive_elements"], "Country")
        browser.execute_action({"type": "select", "element_id": country["id"], "text": "India"}, snapshot["interactive_elements"])
        assert browser.page.locator("select").input_value() == "India"

        browser.goto(page_url("checkbox.html"))
        snapshot, _ = browser.page_snapshot([])
        terms = find(snapshot["interactive_elements"], "terms")
        browser.execute_action({"type": "check", "element_id": terms["id"]}, snapshot["interactive_elements"])
        assert browser.page.locator('[name="terms"]').is_checked()

        browser.goto(page_url("new-tab.html"))
        snapshot, _ = browser.page_snapshot([])
        link = find(snapshot["interactive_elements"], "provider")
        browser.execute_action({"type": "click", "element_id": link["id"]}, snapshot["interactive_elements"])
        assert "success.html" in browser.current_url()
    finally:
        browser.close()


def test_hybrid_vision_and_signals() -> None:
    browser = BrowserEngine(Config(headless=True, human_typing=False))
    try:
        browser.launch()
        browser.goto(page_url("canvas_ui.html"))
        snapshot, _ = browser.page_snapshot([])
        assert snapshot["engine"] == "vision"
        done, result = browser.execute_action({"type": "vision_click", "x": 450, "y": 245}, snapshot["interactive_elements"])
        assert not done
        assert result == "ok"
        assert "successfully" in browser.visible_text().lower()

        browser.goto(page_url("infinite_scroll.html"))
        before = browser.page.evaluate("() => scrollY")
        browser.execute_action({"type": "scroll", "x": 300, "y": 400, "direction": "down"}, [])
        assert browser.page.evaluate("() => scrollY") > before
    finally:
        browser.close()


def test_worker_detection_and_loop_memory() -> None:
    from worker import LinkPilotWorker

    worker = LinkPilotWorker(Config())
    assert worker.prepare_action({"type": "click", "element_id": "el_001"})["type"] == "dom_click"
    assert worker.detect_result({"title": "", "url": "", "visible_text": "Cloudflare Turnstile CAPTCHA"})["status"] == "captcha_required"
    assert worker.detect_result({"title": "", "url": "", "visible_text": "Enter verification code"})["status"] == "otp_required"
    for _ in range(3):
        worker.update_memory({"url": "https://x.test", "title": "Same"}, "abc")
    assert worker.detect_loop() in {"visited_pages", "screenshots", "titles"}


if __name__ == "__main__":
    test_registration_form()
    test_select_check_and_new_tab()
    test_hybrid_vision_and_signals()
    test_worker_detection_and_loop_memory()
    print("browser ok")
