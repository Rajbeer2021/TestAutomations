import logging
import os
import time
import threading
import uuid
from datetime import datetime
from colorama import Fore, Style
from playwright.sync_api import Page
import html as _html
from utils.actionUtils import sanitize_filename
from utils.customdashboard import DashboardGenerator
import sys

# ----------------- Module-level FS Lock -----------------
_fs_lock = threading.Lock()

def format_duration(ms: int) -> str:
    """
    Convert duration in milliseconds to a human-readable string.
    Examples:
        45_000 ms -> "45 sec"
        125_000 ms -> "2 min 5 sec"
        3_600_000 ms -> "1 hr 0 min 0 sec"
    """
    total_seconds = int(ms / 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours} hr")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes} min")
    parts.append(f"{seconds} sec")

    return " ".join(parts)


# ----------------- Colors -----------------
class Colors:
    BRIGHT_YELLOW = "\033[93m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    CYAN = "\033[96m"
    DIM_WHITE = "\033[2;37m"
    RESET = "\033[0m"
    WHITE_DIM = "\033[37;2m"





# ----------------- Custom Reporter -----------------
class CustomReporter:
    _thread_local = threading.local()  # thread-safe storage for parallel runs

    def __init__(self, base_dir="reports/custom_reports",
                 environment="QA",
                 executed_by="Automation",
                 browser="N/A"):

        # --------- Directory & Metadata ---------
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.suite_results = {}
        self.current_suite = None
        self.current_test = None
        self.browser = browser
        self.environment = environment
        self.executed_by = executed_by
        self._fs_lock = _fs_lock  # module-level lock

        # --------- Thread-local storage for screenshots/paths ---------
        self._thread_local = threading.local()

        # --------- Logger setup (console & color support) ---------
        self.logger = logging.getLogger("CustomReporter")
        self.logger.setLevel(logging.INFO)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formatter with timestamp
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)-8s - %(message)s',
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self.pytest_nodeid = None

    def start_suite(self, suite_name):
        logging.info(f"===== Starting Suite: {suite_name} | Browser: {self.browser} =====")



    # ------------------- Start Test -------------------
    def start_test(self, test_case_title: str, suite_name="DefaultSuite", skip: bool = False, skip_reason: str = ""):
        self.current_suite = suite_name
        if suite_name not in self.suite_results:
            self.suite_results[suite_name] = []

        self.current_test = {
            "name": test_case_title,
            "steps": [],
            "status": "SKIP" if skip else "PASS",
            "start_time": datetime.now(),
            "end_time": None,
            "duration": None,
            "skip_reason": skip_reason if skip else None,
        }
        self._thread_local.captured_paths = {}

        if self.pytest_nodeid:
            self.logger.info(f"{Colors.WHITE_DIM}{self.pytest_nodeid}{Colors.RESET}")

        self.logger.info("")  # blank line before test title
        self.logger.info(f"{Colors.CYAN}[START TEST] {test_case_title}{Colors.RESET}")

        # Skipped test
        if skip:
            self.current_test["end_time"] = datetime.now()
            elapsed = (self.current_test["end_time"] - self.current_test["start_time"]).total_seconds()
            self.current_test["duration"] = round(elapsed, 3)
            self.logger.info(
                f"{Style.BRIGHT}{Fore.YELLOW}[END TEST] {test_case_title} — SKIPPED ({self.current_test['duration']}s){Style.RESET_ALL}\n")
            self.suite_results[self.current_suite].append(self.current_test)
            self.current_test = None

    # ------------------- End Step -------------------
    def end_step(self, step_name: str, status: str = "PASS"):
        if not self.current_test:
            return

        step_time = datetime.now()
        status_upper = status.upper()

        # Append step info
        self.current_test["steps"].append({
            "name": step_name,
            "status": status_upper,  # ensure consistency: PASS, FAIL, SKIP
            "time": step_time.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.milliseconds
        })

        # Update current test status if needed
        if status_upper == "FAIL":
            self.current_test["status"] = "FAIL"
        elif status_upper in ["SKIP", "SKIPPED"]:
            # Mark current test as SKIP only if it’s not already FAIL
            if self.current_test.get("status") != "FAIL":
                self.current_test["status"] = "SKIP"

        # Logging
        if status_upper == "PASS":
            self.logger.info(f"[START STEP] {step_name}")
        elif status_upper == "FAIL":
            self.logger.error(f"[END STEP] {step_name} — {status_upper}")
        elif status_upper in ["SKIP", "SKIPPED"]:
            self.logger.warning(f"[SKIP STEP] {step_name} — {status_upper}")

    def end_test(self):
        if not self.current_test:
            return

        self.current_test["end_time"] = datetime.now()
        elapsed = (self.current_test["end_time"] - self.current_test["start_time"]).total_seconds()
        self.current_test["duration"] = round(elapsed, 3)  # seconds.milliseconds

        # Determine status
        status = self.current_test.get("status", "").upper()  # ensure uppercase for comparison

        if status in ["SKIP", "SKIPPED"]:  # handle skipped tests
            color = Fore.YELLOW
            style = Style.BRIGHT
            status_text = "SKIPPED"
            self.current_test["status"] = "SKIP"
        elif any(step.get("status") == "FAIL" for step in self.current_test["steps"]):
            self.current_test["status"] = "FAIL"
            color = Fore.RED
            style = Style.BRIGHT
            status_text = "FAIL"
        else:
            self.current_test["status"] = "PASS"
            color = Fore.GREEN
            style = Style.BRIGHT
            status_text = "PASS"

        # Log end test with duration in seconds.milliseconds
        self.logger.info(
            f"{style}{color}[END TEST] {self.current_test['name']} — {status_text} ({self.current_test['duration']}s){Style.RESET_ALL}\n"
        )

        # Save current test in suite results
        if self.current_suite not in self.suite_results:
            self.suite_results[self.current_suite] = []
        self.suite_results[self.current_suite].append(self.current_test)

        # Clear captured paths and current test
        self._thread_local.captured_paths.clear()
        self.current_test = None

    # ------------------- Capture Step -------------------
    def capture_step(
            self,
            step_name: str,
            page: Page = None,
            status_override=None,
            error_message=None,
            error_type=None,
            stacktrace=None
    ):
        if self.current_test is None:
            self.start_test("unnamed_test", suite_name=self.current_suite or "default_suite")

        status = (status_override or "PASS").upper()
        safe_step = sanitize_filename(step_name)
        key = f"{self.current_suite}:{self.current_test['name']}:{safe_step}"
        self._thread_local.captured_paths = getattr(self._thread_local, "captured_paths", {})

        screenshot_rel_path = self._thread_local.captured_paths.get(key, "")

        if not screenshot_rel_path and status in ["PASS", "FAIL"]:
            if page and not page.is_closed():
                try:
                    file_name = f"{safe_step}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.png"
                    file_path = os.path.join(self._get_screenshots_dir(), file_name)
                    with self._fs_lock:
                        page.screenshot(path=file_path, timeout=15000)
                    screenshot_rel_path = os.path.relpath(file_path,
                                                          os.path.join(self.base_dir, self.current_suite)).replace("\\",
                                                                                                                   "/")
                    self._thread_local.captured_paths[key] = screenshot_rel_path
                except Exception:
                    screenshot_rel_path = "ERROR_SAVING_SCREENSHOT"
            else:
                screenshot_rel_path = "NO_PAGE_AVAILABLE"
        elif status == "SKIP":
            screenshot_rel_path = "STEP_SKIPPED"

        step_entry = {
            "name": step_name,
            "status": status,
            "screenshot": screenshot_rel_path,
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],  # HH:MM:SS.milliseconds
        }

        if status == "FAIL":
            step_entry["error_type"] = error_type or ""
            step_entry["error_message"] = error_message or ""
            step_entry["stacktrace"] = stacktrace or ""
            self.current_test["status"] = "FAIL"
        elif status == "SKIP" and self.current_test.get("status") == "PASS":
            self.current_test["status"] = "SKIP"

        self.current_test["steps"].append(step_entry)

    # ------------------- Screenshots dir -------------------
    def _get_screenshots_dir(self) -> str:
        suite_name = self.current_suite or "default_suite"
        screenshots_dir = os.path.join(self.base_dir, suite_name, "screenshots")
        with self._fs_lock:
            os.makedirs(screenshots_dir, exist_ok=True)
        return screenshots_dir

    def write_dashboard(self):
        """Generate dashboard after all reports are written."""
        try:
            dashboard = DashboardGenerator(base_dir=self.base_dir)
            dashboard.generate_dashboard()
            # print(
            #     f"[INFO] Custom dashboard generated at: "
            #     f"{os.path.join(self.base_dir, 'customdashboard.html')}"
            # )
        except Exception as e:
            print(f"[WARN] Could not generate dashboard: {e}")


    # ------------------- Generate Suite Report -------------------
    def write_suite_report(self, suite_name: str):
        """
        Build an HTML report for the given suite using stored self.suite_results[suite_name].
        This preserves your previous HTML/CSS structure and theme toggle.
        """

        suite_dir = os.path.join(self.base_dir, suite_name)
        # ensure suite dir exists (locked)
        with self._fs_lock:
            os.makedirs(suite_dir, exist_ok=True)

        report_file = os.path.join(suite_dir, f"{suite_name}_report.html")
        dashboard_path = os.path.join(self.base_dir, "dashboard.html")
        rel_dashboard_path = os.path.relpath(dashboard_path, suite_dir).replace("\\", "/")

        suite_tests = self.suite_results.get(suite_name, [])

        total_tests = len(suite_tests)
        passed = sum(1 for t in suite_tests if str(t.get("status", "")).upper() == "PASS")
        failed = total_tests - passed

        total_time = sum(int((t.get("duration", 0) or 0) * 1000) for t in suite_tests)

        #total_time_ms = sum(int((t.get("duration", 0) or 0) * 1000) for t in suite_tests)
        #total_time = format_duration(total_time_ms)  # human-readable

        start_time = ""
        end_time = ""
        if suite_tests:
            try:
                start_time_dt = min(t.get("start_time") for t in suite_tests if t.get("start_time"))
                start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                start_time = ""
            try:
                end_time_dt = max(t.get("end_time") for t in suite_tests if t.get("end_time"))
                end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                end_time = ""

        # Build HTML (kept your original layout & styles) with improved error block (concise + embedded expansion)
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
        <meta charset="UTF-8">
        <title>{_html.escape(suite_name)} - Extent Style Report</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
          body {{
            font-family: 'Segoe UI', sans-serif;
            margin: 0;
            background-color: #0b0f19;
            color: #e2e8f0;
            transition: background 0.4s, color 0.4s;
          }}
          body.light {{
            background-color: #f8fafc;
            color: #1e293b;
          }}
          .toggle-theme {{
            position: fixed;
            top: 15px;
            right: 25px;
            background: #2563eb;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            font-size: 12px;
          }}
          .toggle-theme:hover {{
            background: #1e40af;
          }}
          .sidebar {{
            min-height: 100vh;
            background: linear-gradient(180deg, #111827, #1f2937);
            color: #9ca3af;
            padding: 20px;
            border-right: 1px solid #374151;
            transition: background 0.4s, color 0.4s;
            display: flex;
            flex-direction: column;
          }}
          body.light .sidebar {{
            background: linear-gradient(180deg, #e2e8f0, #f8fafc);
            color: #1e293b;
            border-right: 1px solid #cbd5e1;
          }}
          .sidebar h3 {{
            color: #60a5fa;
            font-weight: 600;
            text-align: center;
            font-size: 18px;
            margin-bottom: 10px;
            cursor: pointer;
          }}
          body.light .sidebar h3 {{
            color: #1e3a8a;
          }}
          .summary-box {{
            background: #1f2937;
            border: 1px solid #374151;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
            font-size: 13px;
            flex-shrink: 0;
          }}
          body.light .summary-box {{
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
          }}
          .summary-box p {{
            margin: 2px 0;
            font-size: 13px;
            font-weight: 500;
          }}
          .summary-box b {{
            font-weight: 600;
          }}
          .sidebar ul {{
            list-style: none;
            padding-left: 0;
            overflow-y: auto;
            flex-grow: 1;
          }}
          .sidebar li {{
            padding: 8px 10px;
            margin: 4px 0;
            border-radius: 6px;
            background: #1e293b;
            cursor: pointer;
            color: #ffffff;
            font-size: 14px;
            font-weight: 500;
            transition: 0.3s;
          }}
          .sidebar li:hover, .active {{
            background: #2563eb;
            color: #fff;
          }}
          body.light .sidebar li {{
            background: #e2e8f0;
            color: #1e293b;
          }}
          body.light .sidebar li.active {{
            background: #3b82f6 !important;
            color: #fff !important;
            box-shadow: 0 0 8px rgba(59,130,246,0.5);
          }}
          .card-custom {{
            background: #1f2937;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            transition: background 0.4s, color 0.4s;
          }}
          body.light .card-custom {{
            background: #ffffff;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
          }}
          table {{
            width: 100%;
            border-collapse: collapse;
          }}
          /* ---------- BLUE SHINY HEADER (dark + light) ---------- */
          thead th {{
            padding: 10px;
            text-align: center;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(90deg, rgba(37,99,235,0.95), rgba(59,130,246,0.95));
            box-shadow: 0 6px 22px rgba(37,99,235,0.08);
            border: none;
          }}
          body.light thead th {{
            color: #ffffff;
            background: linear-gradient(90deg, rgba(59,130,246,0.95), rgba(96,165,250,0.95));
            box-shadow: 0 6px 18px rgba(59,130,246,0.08);
          }}
          td {{
            padding: 10px;
            text-align: center;
            border-bottom: 1px solid #374151;
            color: #e2e8f0;
          }}
          body.light td {{
            color: #1e293b;
            border-bottom: 1px solid #cbd5e1;
          }}
          .badge.PASS {{
            background: linear-gradient(90deg, #10b981, #059669);
            color: #fff;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 600;
          }}
          .badge.FAIL {{
            background: linear-gradient(90deg, #ef4444, #dc2626);
            color: #fff;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 600;
          }}
          .badge.SKIP {{
            background: linear-gradient(90deg, #3b82f6, #60a5fa);
            color: #fff;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 600;
          }}

          .test-detail {{
            display: none;
          }}
          .modal {{
            display: none;
            position: fixed;
            z-index: 9999;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background-color: rgba(0,0,0,0.9);
            justify-content: center;
            align-items: center;
          }}
          .modal img {{
            max-width: 85%;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(37,99,235,0.8);
          }}

          /* ---------- Error panel styles (embedded, animated) ---------- */
          tr.step-row {{
            transition: background 0.18s ease;
          }}
          tr.step-row.fail-row {{
            cursor: pointer;
          }}
          tr.step-row.fail-row:hover {{
            background: rgba(220,38,38,0.04);
          }}
          /* the hidden error row that visually sits under the step row */
          tr.error-row {{
            background: transparent;
          }}
          .error-cell {{
            padding: 0;
            border: none;
            background: transparent;
          }}


/* ------------------------------------------------------- */
/*      DASHBOARD SUMMARY TEXT — THEME ADAPTIVE COLORS     */
/* ------------------------------------------------------- */

/* Dark Theme (default) – bright white text */
.summary-text {{
    color: #f3f4f6 !important;      /* white shine */
    font-size: 16px;
    font-weight: 500;
    line-height: 1.45;
}}

/* Light Theme – clean black text */
body.light .summary-text {{
    color: #111111 !important;      /* black shine */
}}

/* ------------------------------------------------------- */
/*                 SUMMARY BOX — THEME ADAPTIVE            */
/* ------------------------------------------------------- */

/* Default (light mode) */
.summary-box {{
    color: #f3f4f6 !important;      /* white shine */
    font-size: 14px;
    font-weight: 450;

        }}

body.light .summary-box {{
    color: #111111 !important;      /* black shine */
}}


/* ------------------------------------------------------- */
/*             OPTIMIZED THEME-ADAPTIVE ERROR BOX          */
/* ------------------------------------------------------- */

.error-content {{
    margin: 0 12px;
    border-radius: 12px;
    overflow: hidden;

    /* collapsed state */
    max-height: 0;
    padding: 0;
    border: none;

    /* transition effects */
    transition:
        max-height 0.36s ease,
        padding 0.28s ease,
        background 0.3s ease,
        border 0.3s ease,
        color 0.25s ease;

    /* dark theme default */
    background: #0b0f19;
    color: #f3f4f6;

    /* readability */
    font-size: 17px;
    line-height: 1.55;
}}

/* expanded state */
.error-content.open {{
    padding: 16px;
    max-height: 800px;
    border: 1px solid rgba(255,255,255,0.06);
}}

/* ------------------------------------------------------- */
/*                     LIGHT THEME MODE                    */
/* ------------------------------------------------------- */

/* base light mode */
body.light .error-content {{
    background: #ffffff;
    border: none;
}}

/* expanded light mode */
body.light .error-content.open {{
    border: 1px solid rgba(0,0,0,0.08);
}}

/* FORCE ALL INNER TEXT TO BE VISIBLE IN LIGHT MODE */
body.light .error-content,
body.light .error-content *,
body.light .error-content.open,
body.light .error-content.open * {{
    color: #111111 !important;
}}

/* ------------------------------------------------------- */
/*           OPTIONAL: IMPROVE <pre> BLOCK READABILITY      */
/* ------------------------------------------------------- */

.error-content pre {{
    white-space: pre-wrap;        /* wrap long stacktraces */
    word-break: break-word;
    margin: 0;
    padding: 0;
    background: transparent !important;
    color: inherit !important;    /* follows theme color */
    font-family: Consolas, "Courier New", monospace;
}}

/* ---------- FULL-PAGE ERROR MODAL (fills viewport) ---------- */
#fullErrModal {{
  display: none;
  position: fixed;
  z-index: 110000;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(2,6,23,0.88);
  justify-content: center;
  align-items: center;
  padding: 0;
  overflow: auto;
}}

.full-err-box {{
  width: 100%;
  height: 100%;
  overflow: auto;
  border-radius: 0;
  padding: 28px;
  background: #0b0f19;
  color: #f8fafc;
  box-shadow: none;
  display: flex;
  flex-direction: column;
}}

body.light .full-err-box {{
  background: #ffffff;
  color: #0b1220;
}}

.full-err-header {{
  display:flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}}

.full-err-title {{
  font-size: 20px;
  font-weight: 800;
  margin: 0;
}}

.full-err-close {{
  background: transparent;
  border: none;
  color: inherit;
  font-size: 22px;
  cursor: pointer;
  padding: 6px 10px;
}}

.full-err-stack {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", "Courier New", monospace;
  white-space: pre-wrap;
  font-size: 15px;
  line-height: 1.5;
  margin: 0;
  padding: 12px 0 32px 0;
  overflow: auto;
  flex: 1 1 auto;
}}

.full-err-actions {{
  text-align: right;
  margin-top: 12px;
}}

.btn-compact {{
  padding: 6px 10px;
  font-size: 13px;
  border-radius: 6px;
}}

          /* title */
          .error-title {{
            font-weight: 700;
            color: #ffffff;
            font-family: 'Segoe UI', sans-serif;
            margin-bottom: 8px;
            /* subtle shiny effect */
            text-shadow: 0 1px 10px rgba(255,255,255,0.06);
          }}
          /* stack area */
          .error-stack {{
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", "Courier New", monospace;
            font-size: 12px;
            color: #f8fafc;
            line-height: 1.4;
            white-space: pre-wrap;
            overflow: auto;
            max-height: 460px;
            padding-right: 6px;
          }}
          /* reduce visual gap between step and error row */
          tr.step-row + tr.error-row td {{
            padding-top: 0;
          }}
          /* make images not trigger row toggle */
          .screenshot-img {{
            cursor: pointer;
            border-radius: 6px;
          }}
        </style>
        <script>
        function showSummary() {{
          document.getElementById('summaryTable').style.display='table';
          document.querySelectorAll('.test-detail').forEach(t=>t.style.display='none');
          document.querySelectorAll('.sidebar li').forEach(li=>li.classList.remove('active'));
        }}
        function showTest(idx) {{
          document.getElementById('summaryTable').style.display='none';
          document.querySelectorAll('.test-detail').forEach((t,i)=>t.style.display=(i===idx)?'block':'none');
          const sidebarItems = document.querySelectorAll('.sidebar li');
          sidebarItems.forEach((li,i)=>li.classList.toggle('active', i===idx));
        }}
        function openModal(src, ev) {{
          if(ev) ev.stopPropagation();
          const modal = document.getElementById('imgModal');
          document.getElementById('modalImg').src = src;
          modal.style.display = 'flex';
        }}
        function closeModal() {{
          document.getElementById('imgModal').style.display = 'none';
        }}
        function toggleTheme() {{
          document.body.classList.toggle('light');
        }}

        /* Toggle an error panel by id.
           Ensures only one panel is open at a time.
           If the id is already open -> close it.
        */
        function toggleError(id) {{
          const content = document.getElementById(id);
          if(!content) return;
          const isOpen = content.classList.contains('open');
          // close all open panels
          document.querySelectorAll('.error-content.open').forEach(el => el.classList.remove('open'));
          if(!isOpen) {{
            content.classList.add('open');
            // ensure visible
            setTimeout(()=>{{ content.scrollIntoView({{behavior:'smooth', block:'center'}}); }}, 360);
          }}
        }}

        /* Open full-page error modal */
        function openFullError(id, ev) {{
          if(ev) ev.stopPropagation();
          const content = document.getElementById(id);
          if(!content) return;
          const title = content.getAttribute('data-err-title') || '';
          const stack = content.getAttribute('data-err-stack') || '';

          // populate modal
          document.getElementById('fullErrTitle').textContent = title;
          document.getElementById('fullErrStack').textContent = stack;

          // show modal
          const m = document.getElementById('fullErrModal');
          m.style.display = 'flex';
          // prevent body scroll behind modal
          document.body.style.overflow = 'hidden';
        }}

        function closeFullError() {{
          const m = document.getElementById('fullErrModal');
          m.style.display = 'none';
          document.body.style.overflow = '';
        }}

            
        // close full modal when clicking outside box
        document.addEventListener('click', function(e) {{
          const modal = document.getElementById('fullErrModal');
          if(modal && modal.style.display === 'flex') {{
            const box = modal.querySelector('.full-err-box');
            if(box && !box.contains(e.target)) {{
              modal.style.display = 'none';
              document.body.style.overflow = '';
            }}
          }}
        }}, true);
        </script>
        </head>
        <body>
        <button class="toggle-theme" onclick="toggleTheme()">Toggle Theme</button>
        <div class="container-fluid">
          <div class="row g-0">
            <div class="col-md-3 sidebar">
            
              <p><a href="{rel_dashboard_path}" class="btn btn-sm btn-primary w-100 mb-2">View Dashboard</a></p>
              <h3 onclick="showSummary()">Suite: {_html.escape(suite_name)}</h3>
              <div class="summary-box">
               <p><b>Total Tests:</b> {total_tests}</p>
                <p><b>Passed:</b> {passed}</p>
                <p><b>Failed:</b> {failed}</p>
                <p><b>Total Time:</b> {total_time:.3f} ms</p>
                <p><b>Start Time:</b> {start_time}</p>
                <p><b>End Time:</b> {end_time}</p>
                <p><b>Browser:</b> {self.browser}</p>
                <p><b>Environment:</b> {self.environment}</p>
                <p><b>Executed By:</b> {self.executed_by}</p>
              </div>
              <ul>
        """
        # Sidebar test list
        for idx, test in enumerate(suite_tests):
            tname = _html.escape(str(test.get("name", f"test_{idx}")))
            html += f'<li onclick="showTest({idx})">{tname}</li>'
        html += """
              </ul>
            </div>
            <div class="col-md-9 p-4">
              <div class="card-custom mb-4">
                <h4 class="text-center text-info mb-3"> Test Summary </h4>
                <table id="summaryTable" class="table table-hover align-middle">
                  <thead><tr><th>#</th><th>Step</th><th>Status</th><th>Time</th><th>Screenshot</th></tr></thead>
                  <tbody>
        """
        # Summary table rows
        for i, test in enumerate(suite_tests, 1):
            tname = _html.escape(str(test.get("name", f"test_{i}")))
            tstatus = _html.escape(str(test.get("status", "")))
            tdur = f"{float(test.get('duration', 0) or 0):.3f}"
            html += f"<tr onclick='showTest({i - 1})'><td>{i}</td><td>{tname}</td><td><span class='badge {tstatus}'>{tstatus}</span></td><td>{tdur}</td><td></td></tr>"
        html += "</tbody></table></div>"

        # Detailed per-test views
        for idx, test in enumerate(suite_tests):
            test_name_safe = _html.escape(str(test.get("name", f"test_{idx}")))
            test_status = str(test.get("status", ""))
            test_duration = f"{float(test.get('duration', 0) or 0):.3f}"
            html += f"""
            <div class="test-detail">
              <div class="card-custom mb-4">
                <h5 class="text-center">{test_name_safe}</h5>
                <p class="text-center mb-3"><b>Status:</b> <span class='badge {test_status}'>{test_status}</span> | <b>Duration:</b> {test_duration} ms</p>
                <table class="table table-striped align-middle">
                  <thead><tr><th>#</th><th style="text-align:left">Step</th><th>Status</th><th>Time</th><th>Screenshot</th></tr></thead>
                  <tbody>
            """
            steps_list = test.get("steps", []) or []
            for s_idx, step_raw in enumerate(steps_list, 1):
                # Robust normalization: always produce a dict with expected keys
                if isinstance(step_raw, dict):
                    # Ensure keys exist and convert to strings where appropriate
                    step = {
                        "name": step_raw.get("name", "") or "",
                        "status": step_raw.get("status", "") or "",
                        "screenshot": step_raw.get("screenshot", "") or "",
                        "time": step_raw.get("time", "") or "",
                        "error_type": step_raw.get("error_type", "") or "",
                        "error_message": step_raw.get("error_message", "") or "",
                        "stacktrace": step_raw.get("stacktrace", "") or "",
                    }
                else:
                    step = {
                        "name": str(step_raw),
                        "status": "PASS",
                        "screenshot": "",
                        "time": "",
                        "error_type": "",
                        "error_message": "",
                        "stacktrace": "",
                    }

                # safe values
                step_name_html = _html.escape(str(step.get('name', '') or ''))
                step_status = str(step.get('status', '') or '')
                step_time = _html.escape(str(step.get('time', '') or ''))
                screenshot = str(step.get('screenshot', '') or '')
                # safe identifiers for toggle
                err_id = f"err_{idx}_{s_idx}_{uuid.uuid4().hex[:6]}"

                # make step row clickable only if failed
                tr_class = "step-row"
                onclick_attr = ""
                if step_status.upper() == "FAIL":
                    tr_class += " fail-row"
                    onclick_attr = f"onclick=\"toggleError('{err_id}')\""

                # Step row
                html += f"<tr class='{tr_class}' {onclick_attr}>"
                html += f"<td style='width:48px'>{s_idx}</td>"
                html += f"<td style='text-align:left'>{step_name_html}</td>"
                html += f"<td><span class='badge {_html.escape(step_status)}'>{_html.escape(step_status)}</span></td>"
                html += f"<td style='width:110px'>{step_time}</td>"
                html += "<td style='width:120px'>"
                if screenshot and screenshot not in ["NO_PAGE_AVAILABLE", "ERROR_SAVING_SCREENSHOT", ""]:
                    # show image tag; path assumed relative-safe
                    # stopPropagation on click to avoid toggling row
                    html += f"<img src='{_html.escape(screenshot)}' width='100' onclick=\"openModal(this.src, event)\" class='rounded border border-light screenshot-img' style='cursor:pointer'/>"
                elif screenshot == "NO_PAGE_AVAILABLE":
                    html += "<small>no page</small>"
                elif screenshot == "ERROR_SAVING_SCREENSHOT":
                    html += "<small>ss error</small>"
                html += "</td>"
                html += "</tr>"

                # If fail, add error row right below the step row (full-width inside the table)
                if step_status.upper() == "FAIL":
                    # safe extraction of error fields (won't throw)
                    raw_error_type = step.get("error_type", "") or ""
                    raw_stacktrace = step.get("stacktrace", "") or ""

                    # escape for HTML (safe for attributes)
                    esc_error_type = _html.escape(str(raw_error_type))
                    esc_stacktrace = _html.escape(str(raw_stacktrace))

                    # show only error_type + stacktrace (concise as requested)
                    # add data attributes so full-page modal can read them safely
                    html += f"""
                        <tr class="error-row">
                          <td class="error-cell" colspan="5">
                            <div id="{err_id}" class="error-content" data-err-title="{esc_error_type}" data-err-stack="{esc_stacktrace}" onclick="event.stopPropagation();">
                              <div class="error-title">{esc_error_type}</div>
                              <div class="error-stack"><pre style="margin:0;white-space:pre-wrap;">{esc_stacktrace}</pre></div>
                              <div style="margin-top:12px;text-align:right;">
                                <button class="btn btn-sm btn-outline-light btn-compact" onclick="openFullError('{err_id}', event)">Open Full Page</button>
                                <button class="btn btn-sm btn-outline-secondary btn-compact" onclick="toggleError('{err_id}')">Collapse</button>
                              </div>
                            </div>
                          </td>
                        </tr>
                    """

            html += "</tbody></table></div></div>"

        html += """
            </div>
          </div>
        </div>
        <div id="imgModal" class="modal" onclick="closeModal()">
          <img id="modalImg" />
        </div>

        <!-- Full page error modal -->
        <div id="fullErrModal" onclick="/* handled in script */">
          <div class="full-err-box" role="dialog" aria-modal="true">
            <div class="full-err-header">
              <h2 class="full-err-title" id="fullErrTitle"></h2>
              <button class="full-err-close" onclick="closeFullError()" aria-label="Close full error">✕</button>
            </div>
            <pre class="full-err-stack" id="fullErrStack"></pre>
            <div class="full-err-actions">
              <button class="btn btn-sm btn-primary btn-compact" onclick="closeFullError()">Close</button>
            </div>
          </div>
        </div>

        </body></html>
        """

        # ------------------- Write the HTML file -------------------
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[INFO] Extent-style report generated: {report_file}")
        except Exception as e:
            print(f"[ERROR] Failed to write report file: {e}")

        # ------------------- Generate Dashboard after writing HTML -------------------
        self.write_dashboard()
