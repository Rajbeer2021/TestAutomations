import pytest
from utils.customreporter import CustomReporter
from utils.logger import get_logger

# ----------------- Initialize Logger -----------------
logger = get_logger()

# ----------------- BaseTest -----------------
class BaseTest:
    reporter = None
    SUITE_NAME = "DefaultSuite"
    browser_used = "N/A"

    @classmethod
    def setup_class(cls):
        """Initialize reporter once per suite with dynamic browser."""

        # Get browser dynamically if config injected
        if hasattr(cls, "config") and getattr(cls.config, "browser", None):
            cls.browser_used = cls.config.browser
        else:
            cls.browser_used = getattr(cls, "browser_used", "N/A")

        # Initialize reporter if not already
        if cls.reporter is None:
            cls.reporter = CustomReporter(
                base_dir="reports/custom_reports",
                browser=cls.browser_used
            )

        # Suite start message (magenta)

        suite_msg = f"[START SUITE] ===== Starting Suite: {cls.SUITE_NAME}  ====="
        print()
        logger.info(suite_msg)

    @classmethod
    def teardown_class(cls):
        """Write suite report at the end and log End Suite."""

        # Generate suite report
        try:
            if cls.reporter:
                cls.reporter.write_suite_report(suite_name=cls.SUITE_NAME)
                print(f"[INFO] Suite dashboard generated for: {cls.SUITE_NAME}")
        except Exception as e:
            print(f"[ERROR] Writing suite report failed: {e}")

        # Suite end message (magenta)
        suite_msgs = f"[END SUITE] ===== Ending Suite: {cls.SUITE_NAME} ====="
        #print(f"[INFO] {suite_msg}")
        logger.info(suite_msgs)

    @pytest.fixture(autouse=True)
    def inject_config(self, config):
        """Inject configuration (including browser) into each test."""
        self.config = config
        self.env = config.env

        # Update reporter's browser info dynamically
        if self.reporter:
            self.reporter.browser = getattr(config.browser, "type", "N/A")
        yield

    # BaseTest.py (your existing code)
    @pytest.fixture(autouse=True)
    def init_page_and_test(self, browser_page, request):
        """Setup Playwright page + reporting per test function."""
        self.page = browser_page  # <-- shared session page

        test_func = request.function
        test_name = getattr(test_func, "_test_title", request.node.name)

        # Handle skipped tests
        if request.node.get_closest_marker("skip"):
            if self.reporter:
                self.reporter.start_test(test_name, suite_name=self.SUITE_NAME)
                self.reporter.current_test["status"] = "SKIP"
                self.reporter.end_test()
            yield
            return

        # Start test in reporter
        if self.reporter:
            self.reporter.start_test(test_name, suite_name=self.SUITE_NAME)
        yield
        # End test in reporter
        if self.reporter:
            self.reporter.end_test()

