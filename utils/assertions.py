# from typing import Callable, Any, Optional
#
#
# class Assertions:
#     """
#     Centralized Assertions module for Hybrid Framework (UI + API + DB).
#     Handles step-level logging, screenshots, and fallbacks automatically.
#     """
#
#     def __init__(
#         self,
#         page=None,
#         reporter=None,
#         log_func: Optional[Callable[[str, Callable[..., Any], bool], Any]] = None,
#         default_timeout: int = 10000
#     ):
#         self.page = page
#         self.reporter = reporter
#         self.default_timeout = default_timeout
#
#         # Dynamically use injected _log_step or fallback
#         self._log_step: Callable[[str, Callable[..., Any], bool], Any] = (
#             log_func or (lambda step_name, func, screenshot=False: func())
#         )
#
#         # Optional logger (from reporter)
#         self.logger = getattr(reporter, "logger", None)
#
#     # ----------------------------------------------------------------------
#     # Internal Safe Handlers
#     # ----------------------------------------------------------------------
#
#     def _safe_log_step(self, step_name: str, func: Callable, screenshot: bool = False):
#         """
#         Safely executes test steps, catching signature mismatches or logging errors.
#         Accepts any positional/keyword args passed by ActionUtils._log_step.
#         """
#         try:
#             if callable(func):
#                 self._log_step(step_name, lambda *_, **__: func(), screenshot)
#             else:
#                 raise TypeError(f"Expected callable, got {type(func).__name__}")
#         except Exception as e:
#             self._default_log_handler(step_name, func, screenshot)
#             msg = f"[SAFE LOG STEP WARNING] {e}"
#             if self.logger:
#                 self.logger.warning(msg)
#             else:
#                 print(msg)
#
#     def _default_log_handler(self, step_name: str, func: Callable, screenshot: bool = False):
#         """Fallback if _log_step or reporter logging fails."""
#         try:
#             log = self.logger.info if self.logger else print
#             log(f"[START STEP - FALLBACK] {step_name}")
#
#             if callable(func):
#                 func()
#
#             log(f"[END STEP - FALLBACK] {step_name} — PASS")
#
#         except Exception as e:
#             err = f"[FALLBACK ERROR] {step_name}: {str(e)}"
#             if self.logger:
#                 self.logger.error(err)
#             else:
#                 print(err)
#             if screenshot:
#                 self._capture_screenshot(step_name)
#             raise
#
#     def _capture_screenshot(self, step_name: str):
#         """Captures a screenshot on failure."""
#         if not self.page:
#             return
#         try:
#             safe_name = (
#                 step_name.replace(" ", "_")
#                 .replace("/", "_")
#                 .replace("'", "")
#                 .replace("*", "")
#                 .replace(":", "")
#             )
#             path = f"reports/custom_reports/screenshots/assertion_{safe_name}.png"
#             self.page.screenshot(path=path, full_page=True)
#             msg = f"[SCREENSHOT CAPTURED] {path}"
#             if self.logger:
#                 self.logger.info(msg)
#             else:
#                 print(msg)
#         except Exception as e:
#             warn = f"[SCREENSHOT FAILED] {e}"
#             if self.logger:
#                 self.logger.warning(warn)
#             else:
#                 print(warn)
#
#     # ----------------------------------------------------------------------
#     # Generic Assertions
#     # ----------------------------------------------------------------------
#
#     def assertEquals(self, actual, expected, step_name="Assert Equals", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(actual == expected, f"Expected '{expected}', got '{actual}'"), screenshot)
#
#     def assertNotEquals(self, actual, expected, step_name="Assert Not Equals", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(actual != expected, f"Expected not '{expected}'"), screenshot)
#
#     def assertTrue(self, condition, step_name="Assert True", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(condition is True, f"Expected condition to be True"), screenshot)
#
#     def assertFalse(self, condition, step_name="Assert False", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(condition is False, f"Expected condition to be False"), screenshot)
#
#     def assertNull(self, value, step_name="Assert Null", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(value is None, f"Expected value to be None"), screenshot)
#
#     def assertNotNull(self, value, step_name="Assert Not Null", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(value is not None, f"Expected non-null value"), screenshot)
#
#     def assertContains(self, text, substring, step_name="Assert Contains", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(substring in text, f"'{substring}' not found in '{text}'"), screenshot)
#
#     def assertNotContains(self, text, substring, step_name="Assert Not Contains", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(substring not in text, f"'{substring}' unexpectedly found in '{text}'"), screenshot)
#
#     # ----------------------------------------------------------------------
#     # UI Assertions
#     # ----------------------------------------------------------------------
#
#     def assertElementVisible(self, locator, step_name="Assert Element Visible", screenshot=False):
#         def _action():
#             el = self.page.locator(locator)
#             el.wait_for(state="visible", timeout=self.default_timeout)
#             self._assert(el.is_visible(), f"Expected element '{locator}' to be visible")
#         self._safe_log_step(step_name, _action, screenshot)
#
#     def assertElementHidden(self, locator, step_name="Assert Element Hidden", screenshot=False):
#         def _action():
#             el = self.page.locator(locator)
#             el.wait_for(state="hidden", timeout=self.default_timeout)
#             self._assert(not el.is_visible(), f"Expected element '{locator}' to be hidden")
#         self._safe_log_step(step_name, _action, screenshot)
#
#     def assertElementEnabled(self, locator, step_name="Assert Element Enabled", screenshot=False):
#         def _action():
#             self._assert(self.page.locator(locator).is_enabled(), f"Expected '{locator}' to be enabled")
#         self._safe_log_step(step_name, _action, screenshot)
#
#     def assertElementDisabled(self, locator, step_name="Assert Element Disabled", screenshot=False):
#         def _action():
#             self._assert(not self.page.locator(locator).is_enabled(), f"Expected '{locator}' to be disabled")
#         self._safe_log_step(step_name, _action, screenshot)
#
#     def assertTextEquals(self, locator, expected, step_name="Assert Text Equals", screenshot=False):
#         def _action():
#             el = self.page.locator(locator)
#             el.wait_for(state="visible", timeout=self.default_timeout)
#             tag = el.evaluate("el => el.tagName.toLowerCase()")
#             actual = (el.input_value().strip() if tag in ["input", "textarea"] else (el.text_content() or "").strip())
#             self._assert(actual == expected, f"Expected text '{expected}', got '{actual}'")
#         self._safe_log_step(step_name, _action, screenshot)
#
#     def assertURLContains(self, substring, step_name="Assert URL Contains", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(substring in self.page.url, f"'{substring}' not in URL: {self.page.url}"), screenshot)
#
#     def assertTitleEquals(self, expected, step_name="Assert Title Equals", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(self.page.title() == expected, f"Expected title '{expected}', got '{self.page.title()}'"), screenshot)
#
#     def assertElementCount(self, locator, expected_count, step_name="Assert Element Count", screenshot=False):
#         def _action():
#             count = self.page.locator(locator).count()
#             self._assert(count == expected_count, f"Expected {expected_count} elements, found {count}")
#         self._safe_log_step(step_name, _action, screenshot)
#
#     def assertAttributeContains(self, locator, attribute, substring, step_name="Assert Attribute Contains", screenshot=False):
#         def _action():
#             value = self.page.locator(locator).get_attribute(attribute)
#             self._assert(substring in (value or ""), f"Expected '{attribute}' to contain '{substring}', got '{value}'")
#         self._safe_log_step(step_name, _action, screenshot)
#
#     # ----------------------------------------------------------------------
#     # API Assertions
#     # ----------------------------------------------------------------------
#
#     def assertStatusCode(self, response, expected_code, step_name="Assert Status Code", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(response.status_code == expected_code, f"Expected {expected_code}, got {response.status_code}"), screenshot)
#
#     def assertJSONValue(self, response_json, key, expected_value, step_name="Assert JSON Value", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(response_json.get(key) == expected_value, f"Expected '{key}' to be '{expected_value}', got '{response_json.get(key)}'"), screenshot)
#
#     def assertJSONKeyExists(self, response_json, key, step_name="Assert JSON Key Exists", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(key in response_json, f"Missing key '{key}' in response JSON"), screenshot)
#
#     def assertJSONKeyNotExists(self, response_json, key, step_name="Assert JSON Key Not Exists", screenshot=False):
#         self._safe_log_step(step_name, lambda: self._assert(key not in response_json, f"Unexpected key '{key}' in response JSON"), screenshot)
#

