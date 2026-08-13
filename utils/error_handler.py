# utils/error_handler.py
import traceback
import allure
from utils.customreporter import CustomReporter
from playwright.sync_api import Page

def handle_error(
    step_name: str,
    error: Exception,
    page: Page = None,
    reporter: CustomReporter = None,
    take_screenshot: bool = True
):
    """
    Robust error handling for hybrid framework.
    - Logs error to console
    - Captures screenshot if UI step
    - Attaches full traceback to Allure
    - Reports via CustomReporter
    """
    # ----------------- Console Logging -----------------
    error_message = f"[ERROR in {step_name}] {type(error).__name__}: {error}"
    print("\n" + error_message)
    print("Full Traceback:")
    traceback.print_exc()

    # ----------------- Capture Screenshot -----------------
    if page and take_screenshot:
        try:
            screenshot_bytes = page.screenshot(full_page=True)
            allure.attach(
                screenshot_bytes,
                name=f"Screenshot - {step_name}",
                attachment_type=allure.attachment_type.PNG
            )
        except Exception as e:
            print(f"[WARN] Failed to capture screenshot: {e}")

    # ----------------- Attach Full Traceback to Allure -----------------
    try:
        allure.attach(
            traceback.format_exc(),
            name=f"Error details - {step_name}",
            attachment_type=allure.attachment_type.TEXT
        )
    except Exception as e:
        print(f"[WARN] Failed to attach traceback to Allure: {e}")

    # ----------------- Capture in CustomReporter -----------------
    if reporter:
        try:
            reporter.capture_step(
                step_name=f"{step_name} | ERROR: {error}",
                page=page,
                status_override="FAIL"
            )
        except Exception as e:
            print(f"[WARN] Failed to capture error in reporter: {e}")

