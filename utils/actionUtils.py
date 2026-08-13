import os
import re
import time
import uuid
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import allure
from playwright.sync_api import Page
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.customreporter import CustomReporter


# --------------------- Helpers ---------------------------------
class ElementNotFoundError(Exception):
    """Custom exception for element not found."""


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*\']+', "_", name)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.replace(" ", "_").strip("_")
    return sanitized[:200] or "unnamed_step"


# --------------------- ActionUtils Class ------------------------
class ActionUtils:
    _thread_local = threading.local()
    _fs_lock = threading.Lock()
    _global_lock = threading.Lock()
    _any_test_failed = False  # shared fail-fast flag

    DEFAULT_ACTION_RETRY = 6
    DEFAULT_NAV_RETRY = 7
    DEFAULT_RETRY_DELAY = 3
    default_timeout = 15000  # ms

    def __init__(self, page: Page = None, reporter: "CustomReporter" = None, default_timeout: int = 10000):
        self.page: Page = page
        self.reporter: "CustomReporter" = reporter
        self.default_timeout = default_timeout
        self.logger = get_logger(name="PlaywrightLogger", log_file="reports/logs/consolelog.log")
        if self.page:
            setattr(self.page, "_action_utils_instance", self)

    # ---------------- Fail-Fast -----------------
    @classmethod
    def _check_fail_fast(cls):
        with cls._global_lock:
            return cls._any_test_failed

    @classmethod
    def _set_fail_fast(cls):
        with cls._global_lock:
            cls._any_test_failed = True

    # ---------------- Safe Step Logging -----------------
    def _safe_log_step(self, step_name, func, screenshot: Optional[bool] = True):
        retry_log = []
        screenshot_taken = False

        def wrapped_func():
            try:
                return func()
            except Exception as e:
                retry_log.append(str(e))
                raise

        with allure.step(step_name):
            self.logger.info(f"[START STEP] {step_name}")
            try:
                result = wrapped_func()
                if screenshot and not screenshot_taken:
                    self.capture_screenshot(step_name)
                    screenshot_taken = True

                if self.reporter and getattr(self.reporter, "current_test", None):
                    self.reporter.capture_step(step_name, self.page, status_override="PASS")

                if retry_log:
                    allure.attach("\n".join(retry_log), name=f"{step_name} Retry Log",
                                  attachment_type=allure.attachment_type.TEXT)
                return result
            except Exception as e:
                self._set_fail_fast()
                self.logger.error(f"[STEP FAILED] {step_name} — {e}")
                stacktrace = traceback.format_exc()
                if screenshot and not screenshot_taken:
                    self.capture_screenshot(step_name, fail=True)
                if self.reporter and getattr(self.reporter, "current_test", None):
                    self.reporter.capture_step(
                        step_name=step_name,
                        page=self.page,
                        status_override="FAIL",
                        error_message=str(e),
                        stacktrace=stacktrace
                    )
                if retry_log:
                    allure.attach("\n".join(retry_log), name=f"{step_name} Retry Log",
                                  attachment_type=allure.attachment_type.TEXT)
                raise

    # ---------------- Retry Action -----------------
    def _retry_action(
            self,
            action_func,
            step_name,
            retry_count,
            retry_delay: float = None,
            screenshot=True,
            retry_on_assert_fail=False):

        retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        last_exc = None

        # Only retry on real browser/page errors
        retry_signatures = [
            "cannot be reached",
            "ERR_NAME_NOT_RESOLVED",
            "DNS_",
            "net::ERR_",
            "Navigation failed",
            "Timeout exceeded while waiting for event",
            "Target page, context or browser has been closed"
        ]

        for attempt in range(1, retry_count + 1):
            try:
                return action_func()

            except Exception as e:
                last_exc = e
                err = str(e)

                # Do NOT retry when selector takes time
                should_retry = (
                        retry_on_assert_fail or
                        any(sig in err for sig in retry_signatures)
                )

                if should_retry and attempt < retry_count:
                    time.sleep(retry_delay)
                    continue

                break

        raise last_exc

    # ---------------- Page Stabilization -----------------
    def _ensure_page_stable(
            self,
            wait_for_element: Optional[str] = None,
            timeout: Optional[int] = None):

        max_timeout = timeout or getattr(self, "default_timeout", 10000)
        start = time.time()

        broken_signatures = [
            "This site can’t be reached",
            "ERR_NAME_NOT_RESOLVED",
            "DNS_PROBE_FINISHED",
            "net::ERR_"
        ]

        while True:
            try:
                html = self.page.content() or ""

                # Check only for BROKEN PAGE messages
                if any(sig in html for sig in broken_signatures):
                    raise RuntimeError("Page is broken/unreachable")

                # If waiting for element → let Playwright handle visibility
                if wait_for_element:
                    self.page.locator(wait_for_element).wait_for(
                        state="visible",
                        timeout=max_timeout
                    )

                return True

            except Exception:
                if (time.time() - start) * 1000 >= max_timeout:
                    raise
                time.sleep(0.2)

    # ---------------- Screenshot Capture -----------------
    def _get_screenshot_dir(self) -> str:
        base_dir = getattr(self.reporter, "base_dir", "reports/custom_reports") if self.reporter else "reports/custom_reports"
        suite_name = getattr(self.reporter, "current_suite", "default_suite") if self.reporter else "default_suite"
        safe_suite = sanitize_filename(suite_name)
        screenshots_dir = os.path.join(base_dir, safe_suite, "screenshots")
        with ActionUtils._fs_lock:
            os.makedirs(screenshots_dir, exist_ok=True)
        return screenshots_dir

    def capture_screenshot(self, step_name: str = "screenshot", fail: bool = False, full_page: bool = False) -> Optional[str]:
        try:
            screenshots_dir = Path(self._get_screenshot_dir())
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            safe_name = sanitize_filename(step_name)[:200]
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            suffix = "_FAIL" if fail else ""
            filename = f"{safe_name}{suffix}_{timestamp_str}_{uuid.uuid4().hex[:6]}.png"
            full_path = screenshots_dir.joinpath(filename).resolve()

            if getattr(self, "page", None) and not self.page.is_closed():
                with ActionUtils._fs_lock:
                    self.page.screenshot(path=str(full_path), full_page=full_page)
                try:
                    allure.attach.file(str(full_path), name=step_name, attachment_type=allure.attachment_type.PNG)
                except Exception:
                    pass
                if self.reporter:
                    try:
                        self.reporter.register_screenshot(str(full_path), step_name)
                    except Exception:
                        pass
            return str(full_path)
        except Exception as e:
            self.logger.warning(f"[WARN] Screenshot failed for '{step_name}': {e}", exc_info=True)
            return None

    def take_screenshot(self, step_name="screenshot", fail=False, full_page=False):
        """
        Safe wrapper around capture_screenshot(), guaranteed not to crash.
        """

        try:
            # Use existing capture_screenshot
            return self.capture_screenshot(
                step_name=step_name,
                fail=fail,
                full_page=full_page
            )
        except Exception as e:
            self.logger.error(
                f"Failed to take screenshot for '{step_name}': {e}",
                exc_info=True
            )
            return None

    # ---------------- Locator Helpers -----------------
    # -------------------------
    # MAIN RESOLVER
    # -------------------------
    def _resolve_locator(self, locator: str):
        locator = locator.strip()

        # ---------- XPATH ----------
        if locator.startswith("//") or locator.startswith("(//") or locator.startswith(".//"):
            return ("xpath", locator)

        # ---------- ROLE ----------
        # Example: role=button[name="Sign In"]
        if locator.lower().startswith("role="):
            role_selector = locator[5:]
            role, name = self._parse_role(role_selector)
            return ("role", (role, name))

        # ---------- TEXT (exact or partial) ----------
        if locator.lower().startswith("text="):
            return ("text", locator[5:], False)

        # exact text: "Login" or 'Submit'
        if locator.startswith('"') or locator.startswith("'"):
            text_value = locator.strip('"\'')
            return ("text", text_value, True)

        # ---------- PLACEHOLDER ----------
        if locator.lower().startswith("placeholder="):
            return ("placeholder", locator.split("=", 1)[1].strip())

        # ---------- LABEL ----------
        if locator.lower().startswith("label="):
            return ("label", locator.split("=", 1)[1].strip())

        # ---------- ALT TEXT ----------
        if locator.lower().startswith("alt="):
            return ("alt", locator.split("=", 1)[1].strip())

        # ---------- TITLE ATTRIBUTE ----------
        if locator.lower().startswith("title="):
            value = locator.split("=", 1)[1].strip()
            return ("css", f'[title="{value}"]')

        # ---------- DATA-TEST / DATA-ATTR ----------
        if locator.lower().startswith("data-"):
            key, value = locator.split("=", 1)
            return ("css", f'[{key}="{value}"]')

        # ---------- ARIA ----------
        if locator.lower().startswith("aria-"):
            key, value = locator.split("=", 1)
            return ("css", f'[{key}="{value}"]')

        # ---------- ID ----------
        if locator.startswith("#"):
            return ("css", locator)

        if locator.startswith("id="):
            return ("css", f"#{locator[3:]}")

        # ---------- NAME ----------
        if locator.startswith("name="):
            value = locator[5:]
            return ("css", f"[name='{value}']")

        # ---------- CLASS ----------
        if locator.startswith("."):
            return ("css", locator)

        # ---------- GENERIC CSS ----------
        if re.search(r"[.#\[\]>+~]", locator):
            return ("css", locator)

        # ---------- FALLBACK ----------
        return ("text", locator, False)

    def _get_element(self, locator: str):
        sel_type, value, *flags = self._resolve_locator(locator)

        # XPATH
        if sel_type == "xpath":
            return self.page.locator(value)

        # CSS
        if sel_type == "css":
            return self.page.locator(value)

        # ROLE
        if sel_type == "role":
            role, name = value
            return self.page.get_by_role(role, name=name)

        # LABEL
        if sel_type == "label":
            return self.page.get_by_label(value)

        # PLACEHOLDER
        if sel_type == "placeholder":
            return self.page.get_by_placeholder(value)

        # ALT TEXT
        if sel_type == "alt":
            return self.page.get_by_alt_text(value)

        # TEXT (exact / partial)
        if sel_type == "text":
            exact = flags[0] if flags else False
            return self.page.get_by_text(value, exact=exact)

        # FALLBACK: treat as CSS
        return self.page.locator(locator)

    def _parse_role(self, locator: str):
        """
        Parse custom role locator syntax.
        Examples:
            button[name="Sign In"]
            textbox[name='Email']
            link
        """
        locator = locator.strip()

        # Extract role
        if "[" in locator:
            role = locator.split("[")[0].strip()
        else:
            role = locator.strip()

        # Extract name
        name = None
        if "name=" in locator:
            name_part = locator.split("name=")[1].rstrip("]").strip()
            name = name_part.strip('"\' ')  # remove quotes and spaces

        return role.lower(), name

    # ---------------- Core Step Wrapper -----------------
    def _perform_action(self, step_name: str, action_func, wait_for_element: Optional[str] = None,
                        retry_count: Optional[int] = None, retry_delay: Optional[float] = None,
                        screenshot: Optional[bool] = True, retry_on_assert_fail: bool = False):
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        screenshot = True if screenshot is None else screenshot

        def wrapped_action():
            result = action_func()
            self._ensure_page_stable(wait_for_element)
            return result

        return self._safe_log_step(
            step_name,
            lambda: self._retry_action(wrapped_action, step_name, retry_count, retry_delay,
                                       screenshot, retry_on_assert_fail),
            screenshot
        )

    # =================== All UI Steps ===================
    # ---------------- Navigation -----------------
    def step_navigate_to_url(
            self,
            step_name: str,
            url: str,
            wait_for_element: Optional[str] = None,
            retry_count: Optional[int] = None,
            retry_delay: Optional[float] = None,
            screenshot: Optional[bool] = None):

        retry_count = retry_count or self.DEFAULT_NAV_RETRY
        retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        screenshot = True if screenshot is None else screenshot

        def action():
            self.page.goto(url, wait_until="load", timeout=self.default_timeout)

            # ensure element appears AFTER navigation
            if wait_for_element:
                self.page.locator(wait_for_element).wait_for(
                    state="visible",
                    timeout=self.default_timeout
                )

            # ensure page has no broken state
            self._ensure_page_stable(wait_for_element)

            if screenshot:
                self.capture_screenshot(step_name)

            return True

        return self._safe_log_step(
            step_name,
            lambda: self._retry_action(
                action, step_name, retry_count, retry_delay, screenshot
            ),
            screenshot
        )

    def step_click(self, step_name: str, locator: str, timeout: Optional[int] = None,
                   retry_count: Optional[int] = None, retry_delay: Optional[float] = None,
                   wait_for_element: Optional[str] = None, screenshot: Optional[bool] = None):

        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)

            # wait for at least ONE match to be visible
            el.first.wait_for(state="visible", timeout=timeout)

            # click the FIRST visible match
            el.first.click()

            if wait_for_element:
                self._get_element(wait_for_element).first.wait_for(
                    state="visible",
                    timeout=timeout
                )

            self._ensure_page_stable(wait_for_element)
            return True

        return self._safe_log_step(
            step_name,
            lambda: self._retry_action(action, step_name, retry_count, retry_delay, screenshot),
            screenshot
        )


    def step_click_by_role(
            self,
            step_name: str,
            locator: str,
            wait_for_element: Optional[str] = None,
            max_retries: int = 5,
            timeout: Optional[int] = None,
            screenshot: Optional[bool] = None,
    ):
        """
        Smart role-aware click:
        - If locator starts with role= → use get_by_role()
        - Else → fallback to standard resolved element
        - Self-heals broken page with reload()
        - Retries intelligently
        """

        timeout = timeout or self.default_timeout
        screenshot = True if screenshot is None else screenshot

        def resolve_role_locator(role_locator: str):
            """
            Convert role=name="X" → page.get_by_role("role", name="X")
            """
            try:
                if not role_locator.startswith("role="):
                    return None  # not a role selector

                # Example: role=button[name="Login"]
                raw = role_locator.replace("role=", "").strip()

                # Extract role tag
                if "[" in raw:
                    role = raw.split("[")[0]
                else:
                    role = raw

                # Extract name="Value"
                name_val = None
                m = re.search(r'name="([^"]+)"', raw)
                if m:
                    name_val = m.group(1)

                return self.page.get_by_role(role, name=name_val)

            except Exception:
                return None  # fallback to normal _get_element

        def action():
            attempt = 1

            while attempt <= max_retries:
                try:
                    # 1️⃣ Try role-based resolution
                    el = resolve_role_locator(locator)

                    # 2️⃣ If not role-based → fallback to normal locator
                    if not el:
                        el = self._get_element(locator)

                    # Always click FIRST match
                    el.first.wait_for(state="visible", timeout=timeout)
                    el.first.click()

                    # WAIT FOR REQUIRED ELEMENT
                    if wait_for_element:
                        self._get_element(wait_for_element).first.wait_for(
                            state="visible",
                            timeout=timeout
                        )

                    # Stabilize page
                    self._ensure_page_stable(wait_for_element)

                    return True

                except Exception as e:
                    self.logger.warning(
                        f"[RECOVERY] Click failed (attempt {attempt}/{max_retries}): {e}"
                    )

                    # TRY RELOAD & RETRY
                    try:
                        self.page.reload(wait_until="load")
                        self._ensure_page_stable(wait_for_element)
                    except Exception:
                        pass

                    attempt += 1

            # No success → throw
            raise Exception(f"Failed even after {max_retries} retries.")

        return self._safe_log_step(
            step_name,
            lambda: self._retry_action(action, step_name, max_retries, 1.0, screenshot),
            screenshot,
        )

    def step_click_by_lable(self, step_name: str, locator: str,
                                 wait_for_element: Optional[str] = None,
                                 max_retries: int = 5):
        """
        Clicks → waits → if broken page (DNS error / blank page), reloads and retries.
        """

        def action():
            attempt = 1
            while attempt <= max_retries:

                try:
                    # CLICK FIRST VISIBLE MATCH
                    el = self._get_element(locator)
                    el.first.wait_for(state="visible", timeout=self.default_timeout)
                    el.first.click()

                    # WAIT FOR EXPECTED ELEMENT
                    if wait_for_element:
                        self._get_element(wait_for_element).first.wait_for(
                            state="visible",
                            timeout=self.default_timeout
                        )

                    # SUCCESS
                    return True

                except Exception:
                    # PAGE LIKELY BROKEN → try reload
                    self.logger.warning(f"[RECOVERY] Page looks broken. Retry {attempt}/{max_retries}")

                    self.page.reload(wait_until="load")
                    self._ensure_page_stable(wait_for_element)

                    attempt += 1

            # OUT OF RETRIES
            raise Exception(f"Failed even after {max_retries} recovery reload attempts.")

        return self._safe_log_step(
            step_name,
            lambda: self._retry_action(action, step_name, max_retries, 1.0, True),
            True
        )

    def step_type(self, step_name: str, locator: str, textvalue: str, timeout: Optional[int] = None,
                  retry_count: Optional[int] = None, retry_delay: Optional[float] = None,
                  wait_for_element: Optional[str] = None, screenshot: Optional[bool] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.fill("")
            el.type(textvalue, delay=50)
            if wait_for_element:
                self._get_element(wait_for_element).wait_for(state="visible", timeout=timeout)
            self._ensure_page_stable(wait_for_element)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count, retry_delay, screenshot), screenshot)

    def step_reload_page(self, step_name: str = "Reload Page", retry_count: Optional[int] = None,
                         retry_delay: Optional[float] = None, wait_for_element: Optional[str] = None,
                         screenshot: Optional[bool] = None):
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        screenshot = True if screenshot is None else screenshot

        def action():
            self.page.reload(wait_until="load")
            if wait_for_element:
                self._get_element(wait_for_element).wait_for(state="visible", timeout=self.default_timeout)
            self._ensure_page_stable(wait_for_element)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count, retry_delay, screenshot), screenshot)

    # ---------- Keyboard ----------
    def step_press_key(self, step_name: str, locator: str, key: str, screenshot: Optional[bool] = None,
                       timeout: Optional[int] = None, wait_for_element: Optional[str] = None,
                       wait_ms: Optional[int] = 0, pre_screenshot_wait: Optional[int] = 0,
                       retry_count: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.press(key)
            if wait_ms > 0:
                self.page.wait_for_timeout(wait_ms)
            if pre_screenshot_wait > 0:
                self.page.wait_for_timeout(pre_screenshot_wait)
            if wait_for_element:
                self._get_element(wait_for_element).wait_for(state="visible", timeout=timeout)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_press_enter(self, step_name: str, locator: str, screenshot: Optional[bool] = None,
                         timeout: Optional[int] = None, wait_for_element: Optional[str] = None,
                         wait_ms: Optional[int] = 0, pre_screenshot_wait: Optional[int] = 0,
                         retry_count: Optional[int] = None):
        return self.step_press_key(step_name, locator, "Enter", screenshot, timeout,
                                   wait_for_element, wait_ms, pre_screenshot_wait, retry_count)

    # ---------- Hover / Drag ----------
    def step_move_to_element(self, step_name: str, locator: str, screenshot: Optional[bool] = None,
                             timeout: Optional[int] = None, retry_count: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.hover()
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_drag_and_drop(self, step_name: str, source_locator: str, target_locator: str,
                           screenshot: Optional[bool] = None, timeout: Optional[int] = None,
                           retry_count: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY

        def action():
            source = self._get_element(source_locator)
            target = self._get_element(target_locator)
            source.wait_for(state="visible", timeout=timeout)
            target.wait_for(state="visible", timeout=timeout)
            source.drag_to(target)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_hover_and_click(self, step_name: str, locator: str, screenshot: Optional[bool] = None,
                             timeout: Optional[int] = None, retry_count: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.hover()
            el.click()
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_hover_click_and_wait(self, step_name: str, hover_locator: str, click_locator: str,
                                  wait_for_element: str, screenshot: Optional[bool] = False,
                                  timeout: Optional[int] = None, retry_count: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY

        def action():
            hover_el = self._get_element(hover_locator)
            hover_el.wait_for(state="visible", timeout=timeout)
            hover_el.hover()

            click_el = self._get_element(click_locator)
            click_el.wait_for(state="visible", timeout=timeout)
            click_el.click()

            final_el = self._get_element(wait_for_element)
            final_el.wait_for(state="visible", timeout=timeout)

            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    # ---------- Dropdown ----------
    def step_select_dropdown_by_text(self, step_name: str, locator: str, visible_text: str,
                                     screenshot: Optional[bool] = None,
                                     retry_count: Optional[int] = None, timeout: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.select_option(label=visible_text)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_select_dropdown_by_value(self, step_name: str, locator: str, value: str,
                                      screenshot: Optional[bool] = None,
                                      retry_count: Optional[int] = None, timeout: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.select_option(value=value)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_select_dropdown_by_index(self, step_name: str, locator: str, index: int,
                                      screenshot: Optional[bool] = None,
                                      retry_count: Optional[int] = None, timeout: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.select_option(index=index)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    # ---------- File Upload / Download ----------
    def step_upload_file(self, step_name: str, locator: str, file_path: str,
                         screenshot: Optional[bool] = None,
                         retry_count: Optional[int] = None, timeout: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.set_input_files(file_path)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_download_file(self, step_name: str, locator: str, save_path: str,
                           screenshot: Optional[bool] = None,
                           retry_count: Optional[int] = None, timeout: Optional[int] = None):
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot
        save_path = Path(save_path).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)

        def action():
            with self.page.expect_download(timeout=timeout) as download_info:
                self._get_element(locator).click()
            download = download_info.value
            download.save_as(str(save_path))
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    # ---------- Tab / Window ----------
    def step_open_new_tab(self, step_name: str, url: Optional[str] = None,
                          screenshot: Optional[bool] = None, retry_count: Optional[int] = None):
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            new_page = self.page.context.new_page()
            if url:
                new_page.goto(url)
            self.page = new_page
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_close_current_tab(self, step_name: str, switch_to_index: Optional[int] = 0,
                               screenshot: Optional[bool] = None, retry_count: Optional[int] = None):
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            if not self.page.is_closed():
                self.page.close()
            pages = self.page.context.pages
            self.page = pages[switch_to_index] if pages else None
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    # ---------- Alerts ----------
    def step_accept_alert(self, step_name: str, screenshot: Optional[bool] = None,
                          retry_count: Optional[int] = None):
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY

        def action():
            self.page.on("dialog", lambda dialog: dialog.accept())
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    def step_dismiss_alert(self, step_name: str, screenshot: Optional[bool] = None,
                           retry_count: Optional[int] = None):
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY

        def action():
            self.page.on("dialog", lambda dialog: dialog.dismiss())
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, lambda: self._retry_action(action, step_name, retry_count), screenshot)

    # ---------------- Wait Handlers ----------------
    def step_wait_for_element(self, step_name: str, locator: str, timeout: Optional[int] = None,
                              visible: bool = True, retry_count: Optional[int] = None,
                              screenshot: Optional[bool] = None):
        """
        Wait until the element is visible or hidden.
        """
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            state = "visible" if visible else "hidden"
            el.wait_for(state=state, timeout=timeout)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name,
                                   lambda: self._retry_action(action, step_name, retry_count),
                                   screenshot)

    def step_wait_for_text(self, step_name: str, locator: str, expected_text: str, timeout: Optional[int] = None,
                           retry_count: Optional[int] = None, screenshot: Optional[bool] = None):
        """
        Wait until the element contains expected text.
        """
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.wait_for(state="visible", timeout=timeout)
            actual_text = el.inner_text(timeout=timeout)
            if expected_text not in actual_text:
                raise AssertionError(f"Expected text '{expected_text}' not found in element text '{actual_text}'")
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name,
                                   lambda: self._retry_action(action, step_name, retry_count),
                                   screenshot)

    def step_wait_for_attribute(self, step_name: str, locator: str, attribute_name: str, expected_value: str,
                                timeout: Optional[int] = None, retry_count: Optional[int] = None,
                                screenshot: Optional[bool] = None):
        """
        Wait until the element's attribute has the expected value.
        """
        timeout = timeout or self.default_timeout
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot
        poll_interval = 0.5
        max_attempts = int(timeout / (poll_interval * 1000))

        def action():
            el = self._get_element(locator)
            for _ in range(max_attempts):
                val = el.get_attribute(attribute_name)
                if val == expected_value:
                    if screenshot:
                        self.capture_screenshot(step_name)
                    return True
                time.sleep(poll_interval)
            raise AssertionError(f"Attribute '{attribute_name}' did not become '{expected_value}' within {timeout} ms")

        return self._safe_log_step(step_name,
                                   lambda: self._retry_action(action, step_name, retry_count),
                                   screenshot)

    def step_scroll_to_element(self, step_name: str, locator: str, behavior: str = "auto",
                               block: str = "center", inline: str = "center",
                               screenshot: Optional[bool] = None, retry_count: Optional[int] = None):
        """
        Scroll the page until the element is in view.
        """
        retry_count = retry_count or self.DEFAULT_ACTION_RETRY
        screenshot = True if screenshot is None else screenshot

        def action():
            el = self._get_element(locator)
            el.scroll_into_view_if_needed(timeout=self.default_timeout)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name,
                                   lambda: self._retry_action(action, step_name, retry_count),
                                   screenshot)

    def step_wait(self, step_name: str, milliseconds: int, screenshot: Optional[bool] = None):
        """
        Wait for a fixed amount of time.
        """
        screenshot = True if screenshot is None else screenshot

        def action():
            self.page.wait_for_timeout(milliseconds)
            if screenshot:
                self.capture_screenshot(step_name)
            return True

        return self._safe_log_step(step_name, action, screenshot)

    def step_pause(self, seconds: float = 2.0, step_name: str = None, screenshot: bool = False):
        """
        Pause execution for given number of seconds (default = 2s).
        Logs the pause as a test step and optionally captures screenshot.
        """
        step_name = step_name or f"Pause for {seconds} seconds"

        def action():
            time.sleep(seconds)
            return True

        return self._safe_log_step(
            step_name,
            action,  # ✔ correctly passed
            screenshot
        )


    # ---------------- Assertions -----------------
    def assertElementVisible(self, locator, step_name="Assert Element Visible",
                             retry_count: Optional[int] = None, retry_delay: Optional[float] = None,
                             screenshot: Optional[bool] = True):
        return self._perform_action(
            step_name,
            lambda: self._assert_visible(locator),
            retry_count=retry_count,
            retry_delay=retry_delay,
            screenshot=screenshot,
            retry_on_assert_fail=True
        )

    def assertTextEquals(self, locator, expected_text, step_name="Assert Text Equals",
                         retry_count: Optional[int] = None, retry_delay: Optional[float] = None,
                         screenshot: Optional[bool] = True):
        return self._perform_action(
            step_name,
            lambda: self._assert_text_equals(locator, expected_text),
            retry_count=retry_count,
            retry_delay=retry_delay,
            screenshot=screenshot,
            retry_on_assert_fail=True
        )

    def assertTextContains(self, locator, expected_substring, step_name="Assert Text Contains",
                           retry_count: Optional[int] = None, retry_delay: Optional[float] = None,
                           screenshot: Optional[bool] = True):
        return self._perform_action(
            step_name,
            lambda: self._assert_text_contains(locator, expected_substring),
            retry_count=retry_count,
            retry_delay=retry_delay,
            screenshot=screenshot,
            retry_on_assert_fail=True
        )

    def assertTextNotEquals(self, locator, unexpected_text, step_name="Assert Text Not Equals",
                            retry_count: Optional[int] = None, retry_delay: Optional[float] = None,
                            screenshot: Optional[bool] = True):
        return self._perform_action(
            step_name,
            lambda: self._assert_text_not_equals(locator, unexpected_text),
            retry_count=retry_count,
            retry_delay=retry_delay,
            screenshot=screenshot,
            retry_on_assert_fail=True
        )

    # ---------------- Internal Assertion Helpers -----------------
    # ---------------- Internal Assertion Helpers -----------------
    def _assert_visible(self, locator):
        el = self._get_element(locator).first
        el.wait_for(state="visible", timeout=self.default_timeout)
        assert el.is_visible(), f"Expected element '{locator}' to be visible"

    def _assert_text_equals(self, locator, expected_text):
        el = self._get_element(locator).first
        el.wait_for(state="visible", timeout=self.default_timeout)
        actual_text = self._get_element_text(el)
        assert actual_text == expected_text, f"Expected '{expected_text}', got '{actual_text}'"

    def _assert_text_contains(self, locator, expected_substring):
        el = self._get_element(locator).first
        el.wait_for(state="visible", timeout=self.default_timeout)
        actual_text = self._get_element_text(el)
        assert expected_substring in actual_text, f"Expected substring '{expected_substring}' in '{actual_text}'"

    def _assert_text_not_equals(self, locator, unexpected_text):
        el = self._get_element(locator).first
        el.wait_for(state="visible", timeout=self.default_timeout)
        actual_text = self._get_element_text(el)
        assert actual_text != unexpected_text, f"Unexpected text '{unexpected_text}' found in '{actual_text}'"

    def _get_element_text(self, el):
        tag_name = el.evaluate("el => el.tagName.toLowerCase()")
        if tag_name in ["input", "textarea", "select"]:
            return el.input_value().strip()
        else:
            return el.inner_text().strip()

