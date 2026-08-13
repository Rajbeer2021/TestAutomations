# utils/logger.py
import logging
import os
import sys
from colorama import Fore, Style, init

init(autoreset=True)


class StepAwareFormatter(logging.Formatter):
    """
    Special formatter that:
     - prints the test path (tests/...) as a DIM white line on its own
     - prints [START TEST] in bright cyan (no extra blank lines)
     - prints [START STEP] in bright yellow
     - prints [END STEP] PASS in yellow, FAIL in bright red
     - prints [END TEST] in bright green (PASS) or bright red (FAIL), one line
     - generic INFO lines are dim white
    """

    def format(self, record):
        msg = record.getMessage()

        # Base formatted string
        base = f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} - {record.levelname:<8} - {msg}"

        # ---- Suite-level ----
        if "[START SUITE]" in msg or "[END SUITE]" in msg:
            return f"{Style.BRIGHT}{Fore.MAGENTA}{base}{Style.RESET_ALL}"

        # ---- START TEST ----
        if "[START TEST]" in msg:
            return f"{Style.BRIGHT}{Fore.CYAN}{base}{Style.RESET_ALL}"

        # ---- END TEST ----
        if "[END TEST]" in msg:
            if "FAIL" in msg:
                return f"{Style.BRIGHT}{Fore.RED}{base}{Style.RESET_ALL}"
            elif "SKIPPED" in msg:
                return f"{Style.BRIGHT}{Fore.YELLOW}{base}{Style.RESET_ALL}"
            return f"{Style.BRIGHT}{Fore.GREEN}{base}{Style.RESET_ALL}"

        # ---- START STEP ----
        if "[START STEP]" in msg:
            return f"{Style.BRIGHT}{Fore.YELLOW}{base}{Style.RESET_ALL}"

        # ---- END STEP ----
        if "[END STEP]" in msg:
            if "FAIL" in msg:
                return f"{Style.BRIGHT}{Fore.RED}{base}{Style.RESET_ALL}"
            return f"{Style.BRIGHT}{Fore.YELLOW}{base}{Style.RESET_ALL}"

        # ---- Test path line (dim white, timestamp first) ----
        # ---- Test path line (dim white, no timestamp) ----
        if msg.startswith("tests/") and "::" in msg:
            return f"{Style.DIM}{Fore.WHITE}{msg}{Style.RESET_ALL}"

        # ---- Generic INFO ----
        return f"{Style.DIM}{Fore.WHITE}{base}{Style.RESET_ALL}"


def get_logger(name: str = __name__,
               log_file: str = "reports/logs/consolelog.log",
               console: bool = None):
    """
    Centralized logger:
      - File logs always enabled
      - Console logs optional; auto-detects interactive runs
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Remove old handlers to prevent duplicates
    for h in list(logger.handlers):
        logger.removeHandler(h)

    # Auto-detect console logging if console param not provided
    if console is None:
        # Enable console logging if running interactively (not through pytest capture)
        console = sys.stdout.isatty()

    # Console handler (optional)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        try:
            console_formatter = StepAwareFormatter(
                "%(asctime)s - %(levelname)-8s - %(message)s",
                "%Y-%m-%d %H:%M:%S"
            )
        except NameError:
            console_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)-8s - %(message)s",
                "%Y-%m-%d %H:%M:%S"
            )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File handler (always)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s - %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Stop propagation so pytest does not duplicate logs
    logger.propagate = False
    return logger


def close_logger(logger):
    """Cleanly close all handlers."""
    if logger:
        for h in list(logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            logger.removeHandler(h)