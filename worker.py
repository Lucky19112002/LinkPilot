from __future__ import annotations

import base64
import json
import traceback
from datetime import datetime
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QThread, Signal

from api import ApiClient
from browser import BrowserEngine
from crash_handler import save_crash
from config import Config
from ollama_manager import OllamaManager
from plugins import PluginManager
from queue_manager import QueueManager
from secure_store import SecureStore
from telemetry import Telemetry
from version import APP_NAME, BUILD, VERSION
from paths import data_dir


PROMPT = """You are LinkPilot, an autonomous browser agent.
Use the raw screenshot, annotated overlay screenshot, DOM JSON, engine recommendation, and memory to choose exactly one next action.
Return only JSON, no markdown:
{"reason":"short reason","confidence":0.91,"engine":"dom|vision","action":{"type":"dom_click|dom_type|dom_select|dom_check|vision_click|vision_double_click|vision_drag|keyboard|hotkey|scroll|wait|done","element_id":"el_001","x":842,"y":611,"from":{"x":300,"y":500},"to":{"x":900,"y":500},"text":"","keys":["CTRL","L"],"direction":"down","seconds":3}}

Rules:
- Prefer DOM actions when reliable elements exist. Prefer vision actions for canvas, SVG-heavy, shadow DOM, or visually rendered controls.
- Use element_id from interactive_elements for DOM actions.
- Use viewport-relative x/y coordinates for vision actions.
- If unsure, return confidence below 0.50.
- Fill forms from profile values. Do not invent private data.
- Use visible labels, placeholders, aria labels, nearby text, and field purpose to choose fields dynamically.
- Use wait for loading pages. Use scroll when needed.
- Choose done when registration/login/task is complete, blocked by OTP/CAPTCHA, duplicate account, or unrecoverable error.
- Do not attempt to solve CAPTCHA.

Status meanings to recognize:
- success: registration/login/task completed
- otp_required: one-time password, SMS/email code, verification code required
- captcha_required: CAPTCHA/human verification required
- duplicate_account: account already exists/email already used
- error: visible site error or unrecoverable failure

Profile:
{profile}

Page snapshot:
{snapshot}

Memory:
{memory}
"""


class LinkPilotWorker(QObject):
    status_changed = Signal(str)
    log = Signal(str)
    progress = Signal(int)
    current_url = Signal(str)
    queue_count = Signal(int)
    step_changed = Signal(int, int)
    action_changed = Signal(str)
    page_title_changed = Signal(str)
    result_changed = Signal(str)
    metrics_changed = Signal(str)
    queue_changed = Signal(list)
    update_status_changed = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.api = ApiClient(config)
        self.ollama = OllamaManager(config)
        self.telemetry = Telemetry(config)
        self.plugins = PluginManager()
        self.queue = QueueManager()
        self.store = SecureStore()
        self.stop_requested = False
        self.pause_requested = False
        self.memory = {"visited_pages": [], "clicked": [], "filled_fields": [], "screenshots": [], "actions": [], "titles": []}

    def stop(self) -> None:
        self.stop_requested = True

    def set_paused(self, paused: bool) -> None:
        self.pause_requested = paused
        self.queue.paused = paused

    def retry_url(self, url: str) -> None:
        self.queue.retry(url)
        self.queue_changed.emit(self.queue.rows())

    def skip_url(self, url: str) -> None:
        self.queue.skip(url)
        self.queue_changed.emit(self.queue.rows())

    def run_until_empty(self) -> None:
        try:
            self.status_changed.emit("Authenticating")
            self._emit_log("Authenticating")
            auth = self.api.login()
            if auth.get("ok") is False:
                raise RuntimeError("API authentication failed")
            while not self.stop_requested:
                self.status_changed.emit("Fetching URLs")
                urls = self.api.fetch_urls()
                self.queue.load(urls)
                self.queue_changed.emit(self.queue.rows())
                self.queue_count.emit(len(urls))
                self.progress.emit(0)
                if not urls:
                    self.status_changed.emit("Finished")
                    break
                for index, url in enumerate(urls, 1):
                    if self.stop_requested:
                        break
                    while self.pause_requested and not self.stop_requested:
                        self.status_changed.emit("Paused")
                        self.telemetry.maybe_send(self.api, "paused", url)
                        QThread.msleep(1000)
                    if self.queue._item(url).status == "Skipped":
                        continue
                    self.queue.mark(url, "Processing")
                    self.queue_changed.emit(self.queue.rows())
                    self.current_url.emit(url)
                    self.status_changed.emit("Processing URL")
                    result = self.process_url(url)
                    self.queue.mark(url, "Success" if result.get("status") == "success" else "Failed")
                    self.queue_changed.emit(self.queue.rows())
                    self.progress.emit(index)
                    if index < len(urls) and not self.stop_requested:
                        self._wait_after_task()
                if self.stop_requested:
                    self.status_changed.emit("Idle")
                    break
        except Exception as exc:
            self.error.emit(str(exc))
            self._emit_log(f"ERROR {exc}")
            self.status_changed.emit("Idle")
        finally:
            self.finished.emit()

    def process_url(self, url: str) -> dict:
        run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        host = urlparse(url).netloc.replace(":", "_") or "unknown"
        run_dir = data_dir() / "logs" / run_id / host
        run_dir.mkdir(parents=True, exist_ok=True)
        log = run_dir / "execution.log"
        browser = BrowserEngine(self.config)
        last_screenshot = b""
        timeline: list[dict] = []
        final = {
            "url": url,
            "status": "error",
            "steps": 0,
            "final_url": url,
            "message": "Not completed",
        }
        try:
            self._log(log, f"START {APP_NAME} {VERSION} build {BUILD}")
            browser.launch()
            self.plugins.call("before_navigation", url=url, config=self.config)
            browser.goto(url)
            self.plugins.call("after_navigation", url=url, browser=browser)
            self._log(log, f"URL Loaded {url}")
            step = 0
            while step < self.config.max_ai_actions:
                if self.stop_requested:
                    self._log(log, "STOP requested")
                    final["status"] = "stopped"
                    final["message"] = "Stopped by user"
                    break
                step += 1
                step_start = monotonic()
                self.step_changed.emit(step, self.config.max_ai_actions)
                screenshot = run_dir / f"step{step}.png"
                image = browser.screenshot(screenshot)
                last_screenshot = image
                screenshot_hash = browser.screenshot_hash()
                snapshot, dom_seconds = browser.page_snapshot(timeline, run_dir, step)
                overlay = run_dir / f"overlay_step{step}.png"
                overlay_seconds = browser.overlay_screenshot(screenshot, overlay, snapshot["interactive_elements"])
                self.update_memory(snapshot, screenshot_hash)
                self.current_url.emit(snapshot["url"])
                self.page_title_changed.emit(snapshot["title"])
                (run_dir / f"snapshot_step{step}.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
                detected = self.detect_result(snapshot)
                if detected["status"] != "running":
                    final.update(
                        {
                            "status": detected["status"],
                            "steps": step - 1,
                            "final_url": snapshot["url"],
                            "message": detected["message"],
                        }
                    )
                    self._log(log, f"DETECTED {detected['status']} {detected['message']}")
                    if detected["status"] in {"otp_required", "captcha_required"}:
                        self.status_changed.emit("Waiting for OTP" if detected["status"] == "otp_required" else "CAPTCHA required")
                    break
                loop = self.detect_loop()
                if loop:
                    self._log(log, f"LOOP DETECTED {loop}; requesting alternative")
                prompt = PROMPT.format(
                    profile=json.dumps(self.profile_for_prompt(), indent=2),
                    snapshot=json.dumps(snapshot, indent=2),
                    memory=json.dumps({**self.memory, "loop_warning": loop}, indent=2),
                )
                self.plugins.call("before_llm", prompt=prompt, snapshot=snapshot)
                (run_dir / f"llm_prompt_step{step}.txt").write_text(prompt, encoding="utf-8")
                llm_start = monotonic()
                raw = self.ollama.generate_action(prompt, base64.b64encode(image).decode("ascii"))
                llm_seconds = monotonic() - llm_start
                (run_dir / f"llm_raw_step{step}.txt").write_text(json.dumps(raw, indent=2), encoding="utf-8")
                decision = self.parse_decision(raw)
                (run_dir / f"llm_decision_step{step}.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
                action = self.prepare_action(decision.get("action", {}))
                confidence = float(decision.get("confidence", 1.0))
                target = self.action_target(action, snapshot["interactive_elements"])
                self.action_changed.emit(f"{action.get('type', 'unknown')} {target}".strip())
                if confidence < 0.50:
                    self._log(log, f"LOW CONFIDENCE {confidence:.2f}; refreshing once")
                    fresh, _ = browser.page_snapshot(timeline, run_dir, step)
                    snapshot = fresh
                    action = {"type": "wait", "seconds": 1}
                timeline.append(
                    {
                        "step": step,
                        "page_title": snapshot["title"],
                        "reason": decision.get("reason", ""),
                        "action": action.get("type", ""),
                        "engine": decision.get("engine", snapshot.get("engine")),
                        "element": target,
                        "element_id": action.get("element_id", ""),
                        "coordinates": {"x": action.get("x"), "y": action.get("y")},
                        "confidence": confidence,
                        "llm_seconds": round(llm_seconds, 3),
                        "screenshot": screenshot.name,
                        "overlay": overlay.name,
                        "url": snapshot["url"],
                        "result": "planned",
                    }
                )
                (run_dir / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
                action_start = monotonic()
                done, action_result = self.execute_with_recovery(browser, action, snapshot, timeline, log)
                action_seconds = monotonic() - action_start
                metrics = {
                    "llm_time": round(llm_seconds, 3),
                    "dom_extract": round(dom_seconds, 3),
                    "vision_overlay": round(overlay_seconds, 3),
                    "browser_action": round(action_seconds, 3),
                    "total_step": round(monotonic() - step_start, 3),
                }
                timeline[-1]["metrics"] = metrics
                timeline[-1]["result"] = action_result
                self.remember_action(action, target)
                self.metrics_changed.emit(self.metrics_summary(timeline))
                self.telemetry.maybe_send(self.api, "processing", browser.current_url())
                self.plugins.call("after_action", action=action, result=action_result, snapshot=snapshot)
                self._log(log, f"ACTION {action} {target} {action_result} {json.dumps(metrics)}")
                if done:
                    final.update(
                        {
                            "status": "success",
                            "steps": step,
                            "final_url": browser.current_url(),
                            "message": decision.get("reason", "Done"),
                        }
                    )
                    break
                post_action, _ = browser.page_snapshot(timeline, run_dir, step)
                detected = self.detect_result(post_action)
                if detected["status"] != "running":
                    final.update(
                        {
                            "status": detected["status"],
                            "steps": step,
                            "final_url": post_action["url"],
                            "message": detected["message"],
                        }
                    )
                    self.current_url.emit(post_action["url"])
                    self.page_title_changed.emit(post_action["title"])
                    self._log(log, f"DETECTED {detected['status']} {detected['message']}")
                    if detected["status"] in {"otp_required", "captcha_required"}:
                        self.status_changed.emit("Waiting for OTP" if detected["status"] == "otp_required" else "CAPTCHA required")
                    break
                if loop and self.detect_loop():
                    final.update(
                        {
                            "status": "loop_detected",
                            "steps": step,
                            "final_url": browser.current_url(),
                            "message": f"Stopped after repeated state: {loop}",
                        }
                    )
                    break
            else:
                final.update(
                    {
                        "status": "max_steps_reached",
                        "steps": step,
                        "final_url": browser.current_url(),
                        "message": f"Reached max_ai_actions={self.config.max_ai_actions}",
                    }
                )
            self._post_result(final, log)
            self.result_changed.emit(f"{final['status']}: {final['message']}")
            if final["status"] == "success":
                self.plugins.call("on_success", result=final)
            self._log(log, f"FINAL {json.dumps(final)}")
        except Exception as exc:
            (run_dir / "exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
            save_crash(exc, traceback.format_exc(), final.get("final_url", url), final.get("status", "error"), last_screenshot, self.memory)
            try:
                self.api.send_error(str(exc), url)
            except Exception as api_exc:
                self._log(log, f"API error log failed {api_exc}")
            self._log(log, f"ERROR {exc}")
            self.error.emit(str(exc))
            final["message"] = str(exc)
            self._post_result(final, log)
            return final
        finally:
            (run_dir / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
            try:
                browser.export_replay(run_dir)
            except Exception as exc:
                self._log(log, f"Replay export failed {exc}")
            browser.close()
        return final

    def parse_decision(self, raw: dict) -> dict:
        text = raw.get("response", "{}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    def profile_for_prompt(self) -> dict:
        profile = dict(self.config.profile)
        password = self.store.get_password(f"{self.config.credential_id}:profile_password")
        if password:
            profile["password"] = password
        return profile

    def prepare_action(self, action: dict) -> dict:
        kind = action.get("type")
        if kind in {"click", "type", "select", "check"}:
            action["type"] = f"dom_{kind}"
            return action
        if kind not in {
            "dom_click", "dom_type", "dom_select", "dom_check", "vision_click", "vision_double_click",
            "vision_drag", "keyboard", "hotkey", "scroll", "wait", "done"
        }:
            return {"type": "wait", "seconds": 2}
        return action

    def action_target(self, action: dict, elements: list[dict]) -> str:
        if "element_id" not in action and "index" not in action:
            return str(action.get("text", "") or action.get("direction", "") or action.get("seconds", ""))
        try:
            element_id = action.get("element_id") or f"el_{int(action['index']) + 1:03d}"
            element = next(item for item in elements if item["id"] == element_id)
        except (ValueError, StopIteration, TypeError):
            return "invalid element"
        return element.get("text") or element.get("label") or element.get("placeholder") or element.get("name") or element.get("tag", "")

    def execute_with_recovery(self, browser: BrowserEngine, action: dict, snapshot: dict, timeline: list[dict], log: Path) -> tuple[bool, str]:
        last_error = ""
        elements = snapshot["interactive_elements"]
        for attempt in range(self.config.recovery_attempts + 1):
            try:
                done, result = browser.execute_action(action, elements)
                if result != "element not found":
                    return done, result
                last_error = result
            except Exception as exc:
                last_error = str(exc)
            if attempt < self.config.recovery_attempts:
                self._log(log, f"RECOVERY {attempt + 1}: {last_error}")
                recovered, _ = browser.page_snapshot(timeline)
                elements = recovered["interactive_elements"]
        return False, f"failed after recovery: {last_error}"

    def metrics_summary(self, timeline: list[dict]) -> str:
        metrics = [item.get("metrics", {}) for item in timeline if item.get("metrics")]
        if not metrics:
            return "Metrics: -"
        count = len(metrics)
        avg = lambda key: sum(float(item.get(key, 0)) for item in metrics) / count
        return (
            f"Avg LLM {avg('llm_time'):.2f}s | DOM {avg('dom_extract'):.2f}s | "
            f"Overlay {avg('vision_overlay'):.2f}s | Action {avg('browser_action'):.2f}s | Step {avg('total_step'):.2f}s"
        )

    def detect_result(self, snapshot: dict) -> dict:
        text = " ".join([snapshot.get("title", ""), snapshot.get("url", ""), snapshot.get("visible_text", "")]).lower()
        checks = (
            ("captcha_required", ("captcha", "recaptcha", "hcaptcha", "turnstile", "cf-turnstile", "verify you are human", "human verification"), "CAPTCHA required"),
            ("otp_required", ("otp", "one-time password", "verification code", "enter code", "sms code"), "OTP required"),
            ("duplicate_account", ("already exists", "already registered", "email already", "account exists"), "Duplicate account"),
            ("error", ("something went wrong", "try again later", "invalid password", "invalid email", "error occurred"), "Site error detected"),
            ("success", ("welcome", "dashboard", "registration complete", "successfully registered", "account created", "logged in"), "Task completed"),
        )
        for status, needles, message in checks:
            if any(needle in text for needle in needles):
                return {"status": status, "message": message}
        return {"status": "running", "message": ""}

    def update_memory(self, snapshot: dict, screenshot_hash: str) -> None:
        for key, value in (("visited_pages", snapshot["url"]), ("titles", snapshot["title"]), ("screenshots", screenshot_hash)):
            self.memory[key].append(value)
            self.memory[key] = self.memory[key][-10:]

    def remember_action(self, action: dict, target: str) -> None:
        self.memory["actions"].append({"type": action.get("type"), "target": target, "x": action.get("x"), "y": action.get("y")})
        self.memory["actions"] = self.memory["actions"][-10:]
        if action.get("type") in {"dom_click", "vision_click"} and target:
            self.memory["clicked"].append(target)
        if action.get("type") == "dom_type" and target:
            self.memory["filled_fields"].append(target)

    def detect_loop(self) -> str:
        for key in ("visited_pages", "screenshots", "titles"):
            values = self.memory[key][-3:]
            if len(values) == 3 and len(set(values)) == 1:
                return key
        actions = [json.dumps(item, sort_keys=True) for item in self.memory["actions"][-3:]]
        if len(actions) == 3 and len(set(actions)) == 1:
            return "actions"
        return ""

    def _post_result(self, final: dict, log: Path) -> None:
        try:
            self.api.send_result(final)
        except Exception as exc:
            self._log(log, f"API result callback failed {exc}")

    def _log(self, path: Path, message: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = f"[{datetime.now():%H:%M:%S}] {message}"
        with path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
        self.log.emit(line)

    def _emit_log(self, message: str) -> None:
        self.log.emit(f"[{datetime.now():%H:%M:%S}] {message}")

    def _wait_after_task(self) -> None:
        for remaining in range(self.config.wait_after_task, 0, -1):
            if self.stop_requested:
                return
            self.status_changed.emit(f"Waiting {remaining}s")
            QThread.msleep(1000)


Worker = LinkPilotWorker
