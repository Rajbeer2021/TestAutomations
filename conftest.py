import logging
import os
import time
import json
import warnings
import subprocess
import allure
from playwright.sync_api import Browser

from utils.customreporter import CustomReporter
from utils.logger import get_logger, close_logger
from utils.actionUtils import ActionUtils
from colorama import init
import pytest
import shutil
import threading
import yaml
from config.config_loader import ConfigManager
import shutil

init(autoreset=True)

# ---------------- Logger & Folders ----------------
logger = get_logger("conftest", log_file="reports/logs/consolelog.log")
extent_results = []
reports_folder = "reports"
allure_results_dir = os.path.join(reports_folder, "allure-results")
allure_html_dir = os.path.join(reports_folder, "allure-htmlreport")

# ---------------- Global variables ----------------
import builtins
builtins._session_start_time = time.strftime("%c")
builtins._base_url = "N/A"

# Thread-local storage for Playwright
_thread_local = threading.local()



class Colors:
    BRIGHT_YELLOW = "\033[93m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    WHITE_DIM = "\033[37;2m"   # <-- Add this line
    CYAN = "\033[36m"           # For [START TEST] title
    RESET = "\033[0m"



# ---------------- Pytest Configure ----------------
def pytest_configure(config):
    """Global pytest configuration setup with environment customization.

    Responsibilities:
    - store session start time
    - initialize and register CustomReporter (both on config and pytest namespace)
    - setup warnings forwarding into Allure
    - add run metadata
    """

    # ----------------------------------------------------
    # SESSION START TIME
    # ----------------------------------------------------
    if not hasattr(config, "_session_start_time"):
        config._session_start_time = time.strftime("%c")
        builtins._session_start_time = config._session_start_time

    # ----------------------------------------------------
    # REGISTER CUSTOM REPORTER (safe global storage)
    # ----------------------------------------------------
    try:
        if not hasattr(config, "_custom_reporter"):
            config._custom_reporter = CustomReporter()
            logger.info("CustomReporter initialized and attached to pytest config.")
        # also expose on pytest module for hooks that receive TestReport objects
        pytest.custom_reporter = config._custom_reporter
    except Exception as e:
        logger.error(f"Failed to initialize CustomReporter: {e}")

    # ----------------------------------------------------
    # Warnings handling -> forward warnings into allure & logs
    # ----------------------------------------------------
    def warn_with_log(message, category, filename, lineno, file=None, line=None):
        warning_msg = f"[WARNING] {category.__name__}: {message} (File: {filename}, Line: {lineno})"
        logger.warning(warning_msg)
        try:
            os.makedirs(allure_results_dir, exist_ok=True)
            allure.attach(
                warning_msg,
                name=f"Warning - {category.__name__}",
                attachment_type=allure.attachment_type.TEXT,
            )
        except Exception:
            pass

    warnings.showwarning = warn_with_log

    # suppress noisy warnings commonly seen in frameworks
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", message=".*async.*", category=UserWarning)
    warnings.filterwarnings("ignore", message=".*loop.*", category=RuntimeWarning)

    # --- Metadata setup (Allure / pytest-html helpers can read this) ---
    if not hasattr(config, "_metadata"):
        config._metadata = {}
    config._metadata.clear()
    config._metadata.update({
        "Date-Time": config._session_start_time,
        "Env": "QA",
        "Host": "wsj.com",
        "Author": "Beer Singh",
        "Testing": "Automation Test",
        "Platform": "Windows-11",
        "Project": "WSJ Customer Center Automation",
        "Framework": "Pytest + Playwright"
    })



# ---------------- Suppress Default PASSED/FAILED ----------------
def pytest_report_teststatus(report, config):
    # Leave default mapping for non-call phases; for call phase return compact status
    if report.when == "call":
        return report.outcome, "", ""


# ==========================================
# MERGED: Screenshot reset + Skip handling
# (runs at setup time for each test)
# ==========================================
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Handle @pytest.mark.skip BEFORE test executes.
    Also fetch the proper '@case_title' for reporting.
    """
    skip_marker = item.get_closest_marker("skip")
    if not skip_marker:
        return

    # Skip reason
    reason = skip_marker.kwargs.get(
        "reason",
        skip_marker.args[0] if skip_marker.args else "Skipped"
    )

    reporter = getattr(pytest, "custom_reporter", None)

    if reporter:
        try:
            suite_name = item.parent.name

            # ---- Fetch Test Case Title ----
            test_func = item.function
            case_title = getattr(test_func, "_test_title", item.name)

            reporter.record_result(
                test_name=case_title,
                status="skipped",
                message=reason,
                duration=0,
                steps=[],
                suite_name=suite_name
            )

            logger.info(f"[INFO] Skipped logged: {case_title} - {reason}")

        except Exception as e:
            logger.warning(f"[WARN] Failed to log skip for {item.name}: {e}")

    # actually skip
    pytest.skip(reason)



# ==========================================
# LOG REPORTS FOR PASSED / FAILED / SKIPPED
# (receives TestReport objects — must NOT expect session attribute)
# ==========================================
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report):

    reporter = getattr(pytest, "custom_reporter", None)
    if reporter is None:
        # reporter not registered — nothing to do
        return

    # Compute test name and suite from nodeid
    node_parts = report.nodeid.split("::")
    suite_name = node_parts[0] if node_parts else "default_suite"
    test_name = node_parts[-1] if node_parts else report.nodeid

    # SKIPPED (setup-phase skip appears with when=='setup' and report.skipped True)
    if report.when == "setup" and getattr(report, "skipped", False):
        try:
            reporter.start_test(test_name, suite_name=suite_name, skip=True, skip_reason=str(report.longrepr))
            reporter._record_result(
                test_name=test_name,
                status="skipped",
                message=str(report.longrepr) if report.longrepr else "",
                duration=0,
                steps=[]
            )
            reporter.end_test()
        except Exception as e:
            logger.debug(f"CustomReporter: failed to record skipped report for {test_name}: {e}")
        return

    # PASS/FAIL (call phase)
    if report.when == "call":
        status = "passed" if getattr(report, "passed", False) else "failed"
        try:
            # gather steps from reporter (if present) and record final result
            steps = []
            try:
                steps = reporter.get_steps_for_test(test_name)
            except Exception:
                # get_steps_for_test may not exist or fail — gracefully continue
                steps = []

            reporter._record_result(
                test_name=test_name,
                status=status,
                message=str(report.longrepr) if getattr(report, "failed", False) else "",
                duration=getattr(report, "duration", 0),
                steps=steps,
            )
            reporter.end_test()
        except Exception as e:
            logger.debug(f"CustomReporter: failed to record call-phase report for {test_name}: {e}")


# ---------------- Session Start: Prepare folders ----------------
def pytest_sessionstart(session):
    """Prepare a new timestamped run folder and move existing reports/logs into it."""

    try:
        timestamp = time.strftime("%Y%m%d_%I_%M_%S_%p")
        new_run_folder = os.path.join(reports_folder, f"latestrun_{timestamp}")
        os.makedirs(new_run_folder, exist_ok=True)

        # Move existing content except previous latestrun folders and symlinks
        if os.path.exists(reports_folder):
            for item in os.listdir(reports_folder):
                item_path = os.path.join(reports_folder, item)
                if item_path == new_run_folder:
                    continue
                if item.startswith("latestrun_"):
                    continue
                if os.path.islink(item_path):
                    continue
                try:
                    shutil.move(item_path, new_run_folder)
                except Exception:
                    # don't fail startup if move fails
                    logger.debug(f"Could not move {item_path} to {new_run_folder}")

        # recreate base run folders
        for folder in [allure_results_dir, allure_html_dir, os.path.join(reports_folder, "custom_reports"), os.path.join(reports_folder, "logs")]:
            os.makedirs(folder, exist_ok=True)

        # optional 'latest' symlink
        latest_link = os.path.join(reports_folder, "latest")
        try:
            if os.path.exists(latest_link) or os.path.islink(latest_link):
                try:
                    os.unlink(latest_link)
                except Exception:
                    pass
            # create symlink only if platform supports it
            try:
                if not os.path.exists(latest_link):
                    os.symlink(reports_folder, latest_link, target_is_directory=True)
            except Exception:
                # ignore on Windows without privileges
                pass
        except Exception:
            pass

        # store globals
        builtins._current_run_dir = reports_folder
        builtins._allure_results_dir = allure_results_dir
        builtins._allure_html_dir = allure_html_dir
        builtins._custom_reports_dir = os.path.join(reports_folder, "custom_reports")
        builtins._logs_dir = os.path.join(reports_folder, "logs")

        logger.info("Reports folders are ready for current run.")

    except Exception as e:
        logger.error(f"Session Start Report Setup -> {e}")


# ---------------- CLI Options ----------------
def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None,
                     help="Environment to run tests: dev | qa | prod")
    parser.addoption("--mybrowser", action="store", default=None,
                     help="Override browser from YAML: chrome | edge | chromium | firefox | webkit")
    parser.addoption("--myheadless", action="store_true", default=None,
                     help="Override headless mode from YAML")
    parser.addoption("--baseurl", action="store", default="", help="Base URL of AUT")
    parser.addoption("--login", action="store_true", default=False, help="Perform login setup")
    parser.addoption("--allure-path", action="store", default=r"D:\ATools\allure-2.32.0\bin\allure.bat",
                     help="Path to Allure CLI")
    parser.addoption("--record-video", action="store", default="false", help="Enable video recording")


@pytest.fixture(scope="session", autouse=True)
def browser_config(request):
    # Access request.config to get CLI option
    browser = request.config.getoption("--mybrowser")
    # store it globally on pytest namespace or BaseTest for later
    return browser

# ---------------- Config Fixture ----------------
class DotDict:
    """Simple dict wrapper for dot-access"""
    def __init__(self, d):
        for k, v in d.items():
            if isinstance(v, dict):
                v = DotDict(v)
            setattr(self, k, v)


@pytest.fixture(scope="session")
def config(pytestconfig):
    """
    Load config.yaml once per session and override settings from CLI options.
    Supports --env, --mybrowser, --myheadless, --baseurl.
    Also loads pytest suite settings like markers, parallel, reruns, default_suite.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(base_dir, "config", "config.yaml")

    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Config file not found: {yaml_path}")

    with open(yaml_path, "r") as f:
        yaml_data = yaml.safe_load(f)

    # ---------------- Environment ----------------
    cli_env = pytestconfig.getoption("--env")
    env_name = cli_env if cli_env else yaml_data.get("default", "dev")
    yaml_data["default"] = env_name

    # Validate environment exists
    if env_name not in yaml_data.get("environments", {}):
        raise ValueError(f"Environment '{env_name}' not found in config.yaml")

    # ---------------- Browser ----------------
    browser_data = yaml_data.get("browser", {})
    cli_browser = pytestconfig.getoption("--mybrowser")
    if cli_browser:
        browser_data["type"] = cli_browser

    cli_headless = pytestconfig.getoption("--myheadless")
    if cli_headless is not None:
        browser_data["headless"] = cli_headless

    yaml_data["browser"] = browser_data

    # ---------------- Base URL Override ----------------
    cli_baseurl = pytestconfig.getoption("--baseurl")
    if cli_baseurl:
        yaml_data["environments"][env_name]["base_url"] = cli_baseurl

    # ---------------- Pytest / Suite Settings ----------------
    pytest_cfg = yaml_data.get("pytest", {})
    yaml_data["pytest"]["active_markers"] = pytest_cfg.get("markers", [])
    yaml_data["pytest"]["default_suite"] = pytest_cfg.get("default_suite", "DefaultSuite")
    yaml_data["pytest"]["parallel"] = pytest_cfg.get("parallel", 1)
    yaml_data["pytest"]["reruns"] = pytest_cfg.get("reruns", 0)
    yaml_data["pytest"]["addopts"] = pytest_cfg.get("addopts", "")

    # ---------------- Return ConfigManager ----------------
    cfg = ConfigManager(yaml_data)
    return cfg


# ---------------- Browser Fixture (one per session) ----------------
@pytest.fixture(scope="session")
def browser_instance(config):
    """Launch a single browser for the whole session"""
    from playwright.sync_api import sync_playwright
    import threading

    if not hasattr(_thread_local, "playwright"):
        _thread_local.playwright = sync_playwright().start()
    p = _thread_local.playwright

    browser_name = config.browser.type.lower()
    headless = config.browser.headless
    slow_mo = getattr(config.browser, "slow_mo", 0)
    launch_kwargs = {"headless": headless, "slow_mo": slow_mo, "args": ["--start-maximized"]}

    if browser_name in ["chrome", "chromium"]:
        browser_type = p.chromium
        if browser_name == "chrome":
            launch_kwargs["channel"] = "chrome"
    elif browser_name in ["edge", "msedge"]:
        browser_type = p.chromium
        launch_kwargs["channel"] = "msedge"
    elif browser_name == "firefox":
        browser_type = p.firefox
    elif browser_name == "webkit":
        browser_type = p.webkit
    else:
        raise ValueError(f"Unsupported browser: {browser_name}")

    browser = browser_type.launch(**launch_kwargs)
    yield browser

    try:
        browser.close()
    except Exception:
        pass
    try:
        _thread_local.playwright.stop()
    except Exception:
        pass

VIDEO_DIR = "reports/videos"

@pytest.fixture(scope="session")
def browser_page(browser_instance: Browser, request, config):
    """
    Single Playwright page for the entire test session.
    Records a single video for the whole suite with a standard name.
    """
    # --- Check if video recording is enabled ---
    video_enabled = getattr(config, "video", False)
    cli_video = request.config.getoption("--video", None)
    if cli_video is not None:
        video_enabled = str(cli_video).lower() in ["true", "on"]

    context_kwargs = {"no_viewport": True}
    if video_enabled:
        os.makedirs(VIDEO_DIR, exist_ok=True)
        context_kwargs["record_video_dir"] = VIDEO_DIR
        context_kwargs["record_video_size"] = {"width": 1280, "height": 720}
        print("\n[INFO] 🎥 Video recording ENABLED for this suite\n")

    # --- Create context & single page ---
    context = browser_instance.new_context(**context_kwargs)
    page = context.new_page()
    page.set_default_timeout(getattr(request.config, "timeouts", {}).get("default", 15000))

    yield page  # shared across all tests

    # --- Close page & context to finalize video ---
    if not page.is_closed():
        page.close()
    context.close()

    # --- Rename video to a standard name ---
    if video_enabled:
        for folder in os.listdir(VIDEO_DIR):
            folder_path = os.path.join(VIDEO_DIR, folder)
            if os.path.isdir(folder_path):
                for f in os.listdir(folder_path):
                    if f.endswith(".webm"):
                        src = os.path.join(folder_path, f)
                        dst = os.path.join(VIDEO_DIR, f"{request.session.name}_suite_video.webm")
                        shutil.move(src, dst)
        print(f"[INFO] 🎬 Suite video saved at {VIDEO_DIR}/{request.session.name}_suite_video.webm")

# ---------------- Step Logger Fixture ----------------
@pytest.fixture
def logEvent():
    def _log(page, step_name: str, screenshot: bool = False, delay: float = 0.5, reporter=None):
        """Thread-safe, robust step logger with optional screenshot."""
        try:
            logger.info(f"[START STEP] {step_name}")
            with allure.step(step_name):
                if screenshot:
                    if page is None:
                        logger.warning(f"Cannot take screenshot for '{step_name}': page is None")
                    elif page.is_closed():
                        logger.warning(f"Cannot take screenshot for '{step_name}': page is closed")
                    else:
                        try:
                            time.sleep(delay)  # optional wait before screenshot
                            # Use ActionUtils safely
                            ActionUtils.take_screenshot(
                                page=page,
                                name_prefix=step_name,
                                reporter=reporter,
                                avoid_duplicates=True
                            )
                        except Exception as e:
                            logger.error(f"Screenshot failed for step '{step_name}': {e}")
            logger.info(f"[END STEP] {step_name}")
        except Exception as e:
            # Do not fail test, just log
            logger.error(f"[FAILED STEP] {step_name}: {e}")
    return _log


# ---------------- Suite/Test Logging (console friendly) ----------------
_current_suite = None

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    global _current_suite
    suite_name = item.parent.name

    # Start suite logging if new
    if _current_suite != suite_name:
        _current_suite = suite_name
        print()  # blank line before suite
        logging.info(f"[START SUITE] {suite_name}")

    reporter = getattr(item.config, "custom_reporter", None)
    test_title = getattr(item, "custom_title", item.name)

    # Start test
    if reporter:
        reporter.start_test(test_title, suite_name=_current_suite)

    start_time = time.time()
    outcome = yield
    duration = time.time() - start_time

    result = outcome.get_result()
    if getattr(result, "failed", False):
        status = "FAIL"
    elif getattr(result, "skipped", False):
        status = "SKIP"
    else:
        status = "PASS"

    # End test
    if reporter:
        reporter.end_test()


# ---------------- Capture Failures (take screenshots on failures) ----------------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()

    # Only act on call-phase results (not setup/teardown)
    if result.when != "call":
        return

    page = item.funcargs.get("browser_page", None)
    reporter = getattr(item.instance, "reporter", None) if hasattr(item, "instance") else None

    # Only attempt screenshot if test failed
    if result.outcome == "failed":
        if page is None:
            logger.warning(f"No page object found for test '{item.name}'; skipping screenshot.")
        elif page.is_closed():
            logger.warning(f"Page already closed for test '{item.name}'; skipping screenshot.")
        else:
            try:
                # Try to get the ActionUtils instance from the test
                action_util = getattr(item.instance, "action", None)
                if action_util is None:
                    # fallback: use class-level ActionUtils if exists
                    logger.warning(f"No ActionUtils instance found for test '{item.name}', using class method if available.")
                    ActionUtils.take_screenshot(
                        page=page,
                        name_prefix=f"{item.name}_failed",
                        fail=True,
                        reporter=reporter,
                        avoid_duplicates=True
                    )
                else:
                    # Use instance method safely
                    action_util.take_screenshot(
                        page=page,
                        name_prefix=f"{item.name}_failed",
                        fail=True,
                        reporter=reporter,
                        avoid_duplicates=True
                    )
            except Exception as e:
                logger.error(f"Failed to capture failure screenshot for test '{item.name}': {e}")

    # Always append test result to extent_results
    extent_results.append({
        "name": item.name,
        "nodeid": item.nodeid,
        "outcome": result.outcome,
        "location": str(item.location),
        "duration": getattr(result, "duration", 0)
    })


# ---------------- Session Finish ----------------
def pytest_sessionfinish(session, exitstatus):
    try:
        # Allure HTML generation (if results exist)
        if os.path.exists(allure_results_dir) and os.listdir(allure_results_dir):
            logger.info("Generating Allure HTML report...")
            try:
                subprocess.run(
                    [r"D:\allure-2.32.0\bin\allure.bat", "generate", allure_results_dir, "-o", allure_html_dir, "--clean"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                logger.info("Allure HTML report generated successfully.")
            except Exception as e:
                logger.warning(f"Allure generate failed: {e}")

        # Write extent-style json (for any downstream processing)
        if extent_results:
            os.makedirs(allure_html_dir, exist_ok=True)
            with open(os.path.join(allure_html_dir, "extent_custom_report.json"), "w") as f:
                json.dump(extent_results, f, indent=4)
            logger.info("Custom JSON report saved.")

        # If custom reporter is registered, attempt to flush dashboards
        reporter = getattr(pytest, "custom_reporter", None)
        if reporter:
            try:
                reporter.write_dashboard()
            except Exception as e:
                logger.debug(f"Error while generating dashboard from CustomReporter: {e}")

    except Exception as e:
        logger.error(f"Session Finish Error -> {e}")
    finally:
        close_logger(logger)


# ---------------- Pytest HTML Report Title ----------------
@pytest.hookimpl(tryfirst=True)
def pytest_html_report_title(report):
    report.title = "WSJ Customer Center - Test Report 🌗"


# ---------------- Pytest HTML Custom Summary ----------------
@pytest.hookimpl(tryfirst=True)
def pytest_html_results_summary(prefix, summary, postfix):
    session_start_time = getattr(builtins, "_session_start_time", time.strftime("%c"))
    base_url = getattr(builtins, "_base_url", "N/A")

    custom_summary = {
        "Date-Time": session_start_time,
        "Env": "QA",
        "Host": "wsj.com",
        "Author": "Beer Singh",
        "Testing": "Automation Test",
        "Platform": "Windows-11-10.0.26200-SP0",
        "URL": base_url
    }

    summary_html = """
    <div class="summary environment" style="margin-bottom:10px; width:250px;">
        <table style="border:1px solid #444;border-collapse:collapse;width:100%; font-size:12px;">
    """
    for k, v in custom_summary.items():
        summary_html += f"""
        <tr>
            <th style="text-align:left;padding:2px 6px;border:1px solid #555;">{k}</th>
            <td style="padding:2px 6px;border:1px solid #555;">{v}</td>
        </tr>
        """
    summary_html += "</table></div>"
    prefix.append(summary_html)

    toggle_code = """
    <style>
    body { transition: background-color 0.3s, color 0.3s; font-family: 'Segoe UI', Roboto, sans-serif; }
    body.light-mode { background-color: #ffffff !important; color: #000000 !important; }
    body.dark-mode { background-color: #1e1e1e !important; color: #d4d4d4 !important; }
    table{border-collapse:collapse!important;}
    td,th{border:1px solid #3c3c3c!important;padding:6px!important;}
    tr.pass,.passed{background-color:#2e7d32!important;color:#fff!important;}
    tr.fail,.failed{background-color:#c62828!important;color:#fff!important;}
    tr.error{background-color:#8e24aa!important;color:#fff!important;}
    .summary,.environment{border:1px solid #444!important;padding:6px!important;border-radius:6px;}
    #themeToggle{position:fixed;top:10px;right:15px;background-color:#0078d4;color:white;border:none;padding:6px 12px;border-radius:8px;cursor:pointer;z-index:9999;font-size:13px;font-weight:bold;transition:all .3s;}
    #themeToggle:hover{background-color:#005a9e;}
    h1#title { transition: color 0.3s; }
    </style>
    <script>
    document.addEventListener("DOMContentLoaded",function(){
        const btn=document.createElement("button");
        btn.id="themeToggle";
        btn.textContent="🌙 Dark Mode";
        document.body.appendChild(btn);
        const title = document.getElementById("title");
        const mode=localStorage.getItem("theme")||"dark";
        function applyTheme(mode) {
            if(mode==="light"){
                document.body.classList.add("light-mode");
                document.body.classList.remove("dark-mode");
                btn.textContent="☀️ Light Mode";
                if(title) title.style.color="#000000";
            } else {
                document.body.classList.add("dark-mode");
                document.body.classList.remove("light-mode");
                btn.textContent="🌙 Dark Mode";
                if(title) title.style.color="#ffffff";
            }
        }
        applyTheme(mode);
        btn.addEventListener("click",()=>{
            const current = document.body.classList.contains("dark-mode") ? "dark" : "light";
            const newMode = current==="dark" ? "light" : "dark";
            applyTheme(newMode);
            localStorage.setItem("theme", newMode);
        });
    });
    </script>
    """
    postfix.append(toggle_code)
