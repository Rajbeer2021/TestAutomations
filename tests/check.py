# File: tests/print_config.py
import os
import yaml
from config.config_loader import ConfigManager
from typing import Any

# ------------------ Load YAML ------------------
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
yaml_path = os.path.join(base_dir, "config", "config.yaml")

if not os.path.exists(yaml_path):
    raise FileNotFoundError(f"Config file not found: {yaml_path}")

with open(yaml_path, "r") as f:
    config_data = yaml.safe_load(f)

# ------------------ Initialize ConfigManager ------------------
cfg: ConfigManager  # type hint helps IDE know cfg is a ConfigManager
cfg = ConfigManager(config_data)

# ------------------ Optional: tell IDE about env attributes ------------------
cfg.dev: Any
cfg.qa: Any
cfg.prod: Any

# ------------------ Print Active Environment ------------------
print("=== Active Environment ===")
print(f"Name: {cfg.active_env_name}")
print(f"Username: {cfg.env.username}")
print(f"Password: {cfg.env.password}")
print(f"Base URL: {cfg.env.base_url}")
print(f"API Base URL: {cfg.env.api_base_url}")
print(f"Feature Flags: {cfg.env.feature_flags}")
print()

# ------------------ Print Dev Environment ------------------
print("=== DEV Environment ===")
print(f"Username: {cfg.dev.username}")
print(f"Password: {cfg.dev.password}")
print(f"Base URL: {cfg.dev.base_url}")
print(f"API Base URL: {cfg.dev.api_base_url}")
print(f"Feature Flags: {cfg.dev.feature_flags}")
print()

# ------------------ Print QA Environment ------------------
print("=== QA Environment ===")
print(f"Username: {cfg.qa.username}")
print(f"Password: {cfg.qa.password}")
print(f"Base URL: {cfg.qa.base_url}")
print(f"API Base URL: {cfg.qa.api_base_url}")
print(f"Feature Flags: {cfg.qa.feature_flags}")
print()

# ------------------ Print PROD Environment ------------------
print("=== PROD Environment ===")
print(f"Username: {cfg.prod.username}")
print(f"Password: {cfg.prod.password}")
print(f"Base URL: {cfg.prod.base_url}")
print(f"API Base URL: {cfg.prod.api_base_url}")
print(f"Feature Flags: {cfg.prod.feature_flags}")
print()
