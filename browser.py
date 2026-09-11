from __future__ import annotations

import random
import re
import shutil
from pathlib import Path
from time import monotonic, sleep

import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError, sync_playwright

from config import Config


INTERACTIVE_SELECTOR = "a,button,input,textarea,select,[role=button],[role=link],[contenteditable=true]"


class BrowserEngine:
    def __init__(self, config: Config):
        self.config = config
        self._playwright = None
        self.browser = None
        self.context = None
        self.page: Page | None = None

    def launch(self) -> None:
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=self.config.headless)
        self.context = self.browser.new_context(
            viewport={"width": self.config.browser_width, "height": self.config.browser_height}
        )
        self.page = self.context.new_page()

    def goto(self, url: str) -> None:
        assert self.page
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self.wait_until_ready()

    def screenshot(self, path: Path) -> bytes:
        assert self.page
        return self.page.screenshot(path=str(path), full_page=True)

    def viewport_screenshot(self, path: Path) -> bytes:
        assert self.page
        return self.page.screenshot(path=str(path), full_page=False)

    def overlay_screenshot(self, source: Path, target: Path, elements: list[dict]) -> float:
        start = monotonic()
        image = Image.open(source).convert("RGB")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        width, height = image.size
        draw.line((width / 2, 0, width / 2, height), fill=(40, 130, 255), width=1)
        draw.line((0, height / 2, width, height / 2), fill=(40, 130, 255), width=1)
        draw.ellipse((width / 2 - 5, height / 2 - 5, width / 2 + 5, height / 2 + 5), outline=(255, 40, 40), width=2)
        for element in elements[:60]:
            rect = element["rect"]
            x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
            if y > height or x > width:
                continue
            draw.rectangle((x, y, x + w, y + h), outline=(0, 180, 80), width=2)
            draw.text((x + 2, max(0, y - 12)), element["id"], fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
            draw.text((x + 2, y + h + 2), f"{int(x)},{int(y)}", fill=(40, 130, 255), font=font)
        image.save(target)
        return monotonic() - start

    def current_url(self) -> str:
        assert self.page
        return self.page.url

    def title(self) -> str:
        assert self.page
        return self.page.title()

    def visible_text(self) -> str:
        assert self.page
        try:
            return self.page.locator("body").inner_text(timeout=5000)[:6000]
        except PlaywrightError:
            return ""

    def extract_elements(self) -> list[dict]:
        assert self.page
        return self.page.evaluate(
            """
            selector => {
              const xpath = el => {
                if (el.id) return `//*[@id="${el.id}"]`;
                const parts = [];
                for (; el && el.nodeType === Node.ELEMENT_NODE; el = el.parentElement) {
                  let index = 1;
                  for (let sib = el.previousElementSibling; sib; sib = sib.previousElementSibling) {
                    if (sib.tagName === el.tagName) index++;
                  }
                  parts.unshift(`${el.tagName.toLowerCase()}[${index}]`);
                }
                return '/' + parts.join('/');
              };
              const css = el => {
                if (el.id) return `#${CSS.escape(el.id)}`;
                const tag = el.tagName.toLowerCase();
                const name = el.getAttribute('name');
                const type = el.getAttribute('type');
                if (name) return `${tag}[name="${CSS.escape(name)}"]`;
                if (type) return `${tag}[type="${CSS.escape(type)}"]`;
                return tag;
              };
              const labelFor = el => {
                const id = el.id || '';
                if (id) {
                  const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
                  if (label) return label.innerText.trim();
                }
                const wrap = el.closest('label');
                return wrap ? wrap.innerText.trim() : '';
              };
              return Array.from(document.querySelectorAll(selector))
                .map((el, i) => {
                  const r = el.getBoundingClientRect();
                  const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || labelFor(el) || '').trim();
                  return {
                    id: `el_${String(i + 1).padStart(3, '0')}`,
                    index: i,
                    tag: el.tagName,
                    text: text.slice(0, 160),
                    role: el.getAttribute('role') || (el.tagName.toLowerCase() === 'a' ? 'link' : ''),
                    type: el.getAttribute('type') || '',
                    name: el.getAttribute('name') || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    aria_label: el.getAttribute('aria-label') || '',
                    label: labelFor(el).slice(0, 160),
                    xpath: xpath(el),
                    css: css(el),
                    rect: {x: r.x, y: r.y, width: r.width, height: r.height},
                    visible: r.width > 0 && r.height > 0,
                    disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
                    options: el.tagName.toLowerCase() === 'select'
                      ? Array.from(el.options).map(o => o.text).slice(0, 50)
                      : []
                  };
                }).filter(e => e.visible);
            }
            """,
            INTERACTIVE_SELECTOR,
        )

    def form_fields(self) -> list[dict]:
        return [el for el in self.extract_elements() if el["tag"].lower() in {"input", "textarea", "select"}]

    def crop_elements(self, run_dir: Path, step: int, elements: list[dict], limit: int = 20) -> list[dict]:
        assert self.page
        crops = []
        crop_dir = run_dir / "crops"
        crop_dir.mkdir(exist_ok=True)
        for element in elements[:limit]:
            rect = element["rect"]
            if rect["width"] < 2 or rect["height"] < 2:
                continue
            path = crop_dir / f"step{step}_{element['id']}.png"
            try:
                self.page.screenshot(
                    path=str(path),
                    clip={
                        "x": max(0, rect["x"]),
                        "y": max(0, rect["y"]),
                        "width": max(1, rect["width"]),
                        "height": max(1, rect["height"]),
                    },
                )
                crops.append({"id": element["id"], "text": element.get("text", ""), "image": str(path.relative_to(run_dir))})
            except PlaywrightError:
                continue
        return crops

    def page_snapshot(self, history: list[dict], run_dir: Path | None = None, step: int = 0) -> tuple[dict, float]:
        start = monotonic()
        elements = self.extract_elements()
        signals = self.engine_signals(elements)
        snapshot = {
            "url": self.current_url(),
            "title": self.title(),
            "visible_text": self.visible_text(),
            "interactive_elements": elements,
            "form_fields": [el for el in elements if el["tag"].lower() in {"input", "textarea", "select"}],
            "element_crops": self.crop_elements(run_dir, step, elements) if run_dir else [],
            "engine": self.choose_engine(signals),
            "engine_signals": signals,
            "history": history,
        }
        return snapshot, monotonic() - start

    def execute_action(self, action: dict, elements: list[dict]) -> tuple[bool, str]:
        assert self.page
        kind = action.get("type")
        kind = self.normalize_action_type(kind)
        if kind == "done":
            return True, "done"
        if kind in {"scroll", "vision_scroll"}:
            self.scroll_at(int(action.get("x", self.config.browser_width / 2)), int(action.get("y", self.config.browser_height / 2)), -900 if action.get("direction") == "up" else 900)
            self.wait_until_ready()
            return False, "scrolled"
        if kind == "wait":
            self.wait_until_ready(max(1, min(int(action.get("seconds", 3)), 30)) * 1000)
            return False, "waited"
        if kind == "vision_click":
            self.mouse_click(int(action["x"]), int(action["y"]))
            self.wait_until_ready()
            return False, "ok"
        if kind == "vision_double_click":
            self.mouse_double_click(int(action["x"]), int(action["y"]))
            self.wait_until_ready()
            return False, "ok"
        if kind == "vision_drag":
            start, end = action["from"], action["to"]
            self.mouse_drag(int(start["x"]), int(start["y"]), int(end["x"]), int(end["y"]))
            self.wait_until_ready()
            return False, "ok"
        if kind in {"keyboard", "hotkey"}:
            self.hotkey(action.get("keys", []))
            self.wait_until_ready()
            return False, "ok"

        element = self.resolve_element(action, elements)
        if not element:
            return False, "element not found"
        if element.get("disabled"):
            self.wait_for_enabled(element)
        popup_expected = kind == "click" and self._target_blank(element)
        if popup_expected:
            with self.page.expect_popup(timeout=5000) as popup:
                result = self._execute_on_element(kind, element, action)
            self.page = popup.value
        else:
            result = self._execute_on_element(kind, element, action)
        self.adopt_latest_page()
        self.wait_until_ready()
        return False, result

    def normalize_action_type(self, kind: str | None) -> str:
        return {
            "dom_click": "click",
            "dom_type": "type",
            "dom_select": "select",
            "dom_check": "check",
        }.get(kind or "", kind or "")

    def _execute_on_element(self, kind: str, element: dict, action: dict) -> str:
        locator = self.locator_for(element)
        locator.scroll_into_view_if_needed(timeout=8000)
        if kind == "click":
            locator.click(timeout=10000)
        elif kind == "type":
            locator.click(timeout=10000)
            self.human_type(str(action.get("text", "")))
        elif kind == "select":
            locator.select_option(label=str(action.get("text", "")), timeout=10000)
        elif kind == "check":
            locator.check(timeout=10000)
        else:
            return f"unsupported {kind}"
        return "ok"

    def locator_for(self, element: dict):
        assert self.page
        if element.get("xpath"):
            return self.page.locator(f"xpath={element['xpath']}").first
        return self.page.locator(element.get("css", INTERACTIVE_SELECTOR)).first

    def resolve_element(self, action: dict, elements: list[dict]) -> dict | None:
        wanted = action.get("element_id")
        if not wanted and "index" in action:
            wanted = f"el_{int(action['index']) + 1:03d}"
        for element in elements:
            if element["id"] == wanted:
                return element
        return self.fuzzy_element(action, elements)

    def fuzzy_element(self, action: dict, elements: list[dict]) -> dict | None:
        needle = " ".join(str(action.get(k, "")) for k in ("text", "label", "target")).strip().lower()
        role = str(action.get("role", "")).lower()
        if not needle and not role:
            return None
        best = None
        best_score = 0
        for element in elements:
            hay = " ".join(str(element.get(k, "")) for k in ("text", "label", "placeholder", "aria_label", "name")).lower()
            score = len(set(re.findall(r"\w+", needle)) & set(re.findall(r"\w+", hay)))
            if role and role == str(element.get("role", "")).lower():
                score += 1
            if score > best_score:
                best = element
                best_score = score
        return best if best_score else None

    def mouse_move(self, x: int, y: int) -> None:
        assert self.page
        sx, sy = self.config.browser_width / 2, self.config.browser_height / 2
        steps = random.randint(8, 18)
        cx = (sx + x) / 2 + random.randint(-80, 80)
        cy = (sy + y) / 2 + random.randint(-80, 80)
        for i in range(1, steps + 1):
            t = i / steps
            bx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t**2 * x
            by = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t**2 * y
            self.page.mouse.move(bx + random.uniform(-1, 1), by + random.uniform(-1, 1))

    def mouse_click(self, x: int, y: int) -> None:
        assert self.page
        self.mouse_move(x, y)
        self.page.mouse.click(x + random.randint(-2, 2), y + random.randint(-2, 2))

    def mouse_double_click(self, x: int, y: int) -> None:
        assert self.page
        self.mouse_move(x, y)
        self.page.mouse.dblclick(x, y)

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        assert self.page
        self.mouse_move(x1, y1)
        self.page.mouse.down()
        self.mouse_move(x2, y2)
        self.page.mouse.up()

    def scroll_at(self, x: int, y: int, amount: int) -> None:
        assert self.page
        self.mouse_move(x, y)
        self.page.mouse.wheel(0, amount)

    def hotkey(self, keys: list[str]) -> None:
        assert self.page
        names = {"CTRL": "Control", "CMD": "Meta", "COMMAND": "Meta", "ALT": "Alt", "OPTION": "Alt", "SHIFT": "Shift"}
        combo = "+".join(names.get(str(key).upper(), str(key)) for key in keys)
        if combo:
            self.page.keyboard.press(combo)

    def screenshot_hash(self) -> str:
        assert self.page
        import hashlib

        return hashlib.sha256(self.page.screenshot(full_page=False)).hexdigest()[:16]

    def engine_signals(self, elements: list[dict]) -> dict:
        assert self.page
        return self.page.evaluate(
            """
            count => ({
              dom_elements: count,
              canvas: document.querySelectorAll('canvas').length,
              svg: document.querySelectorAll('svg').length,
              shadow_dom: Array.from(document.querySelectorAll('*')).filter(el => el.shadowRoot).length,
              accessibility_labels: document.querySelectorAll('[aria-label],[role]').length
            })
            """,
            len(elements),
        )

    def choose_engine(self, signals: dict) -> str:
        dom_score = signals.get("dom_elements", 0) + signals.get("accessibility_labels", 0)
        vision_score = signals.get("canvas", 0) * 5 + signals.get("svg", 0) * 2 + signals.get("shadow_dom", 0) * 3
        return "vision" if vision_score > dom_score else "dom"

    def export_replay(self, run_dir: Path) -> None:
        frames = [Image.open(path).convert("RGB") for path in sorted(run_dir.glob("step*.png"))]
        if not frames:
            return
        frames[0].save(run_dir / "replay.gif", save_all=True, append_images=frames[1:], duration=1000, loop=0)
        try:
            imageio.mimsave(run_dir / "replay.mp4", [imageio.imread(path) for path in sorted(run_dir.glob("step*.png"))], fps=1)
        except Exception:
            if not shutil.which("ffmpeg"):
                return
            raise

    def human_type(self, text: str) -> None:
        assert self.page
        self.page.keyboard.press("Meta+A")
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Backspace")
        for char in text:
            self.page.keyboard.type(char, delay=random.randint(35, 130) if self.config.human_typing else 0)
            if self.config.human_typing and random.random() < 0.015:
                sleep(random.uniform(0.05, 0.2))

    def wait_until_ready(self, timeout_ms: int = 10000) -> None:
        self.wait_for_navigation(timeout_ms)
        self.wait_for_network_idle(timeout_ms)
        self.wait_for_dom_stable(timeout_ms)
        self.wait_for_spinner_disappear(timeout_ms)

    def wait_for_navigation(self, timeout_ms: int = 10000) -> None:
        assert self.page
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except TimeoutError:
            pass

    def wait_for_network_idle(self, timeout_ms: int = 10000) -> None:
        assert self.page
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except TimeoutError:
            pass

    def wait_for_dom_stable(self, timeout_ms: int = 10000) -> None:
        assert self.page
        deadline = monotonic() + timeout_ms / 1000
        previous = ""
        while monotonic() < deadline:
            current = self.page.evaluate("() => document.body ? document.body.innerText.length + ':' + document.querySelectorAll('*').length : ''")
            if current == previous:
                return
            previous = current
            sleep(0.25)

    def wait_for_spinner_disappear(self, timeout_ms: int = 10000) -> None:
        assert self.page
        try:
            self.page.locator('[aria-busy=true], .spinner, .loading, [role=progressbar]').first.wait_for(state="hidden", timeout=timeout_ms)
        except TimeoutError:
            pass

    def wait_for_enabled(self, element: dict) -> None:
        try:
            self.locator_for(element).wait_for(state="visible", timeout=10000)
        except TimeoutError:
            pass

    def adopt_latest_page(self) -> None:
        if self.context and self.context.pages:
            self.page = self.context.pages[-1]

    def close_finished_tabs(self) -> None:
        if not self.context or not self.page:
            return
        for page in list(self.context.pages):
            if page is not self.page and not page.is_closed():
                try:
                    page.close()
                except PlaywrightError:
                    pass

    def _target_blank(self, element: dict) -> bool:
        try:
            return bool(self.locator_for(element).evaluate("el => el.target === '_blank'"))
        except PlaywrightError:
            return False

    def close(self) -> None:
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self._playwright:
            self._playwright.stop()
