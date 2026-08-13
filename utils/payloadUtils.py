import json
from typing import Any, Union
from pathlib import Path
from copy import deepcopy

class PayloadUtility:
    """
    PayloadUtility for API testing:
    - Load JSON payload from file
    - Get nested objects/keys
    - Update nested values dynamically
    - Return as dict, list, or JSON string
    """

    def __init__(self, base_dir: str = "tests/payloads"):
        self.base_dir = base_dir

    # ---------------- Load JSON payload ----------------
    def load_json(self, filename: str) -> Union[dict, list]:
        path = Path(self.base_dir) / filename
        if not path.exists():
            raise FileNotFoundError(f"Payload file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---------------- Get nested JSON ----------------
    def get_nested(
        self,
        payload: Union[dict, list],
        *keys: Union[str, int]
    ) -> Any:
        """
        Access nested JSON objects/arrays
        Example: get_nested(payload, "user", "address", "street")
        """
        current = payload
        for key in keys:
            if isinstance(current, dict) and isinstance(key, str):
                current = current.get(key)
            elif isinstance(current, list) and isinstance(key, int):
                if 0 <= key < len(current):
                    current = current[key]
                else:
                    raise IndexError(f"Index {key} out of range for array")
            else:
                raise KeyError(f"Cannot access key {key} in {type(current)}")
        return current

    # ---------------- Update nested JSON ----------------
    def set_nested(
        self,
        payload: Union[dict, list],
        value: Any,
        *keys: Union[str, int]
    ) -> Union[dict, list]:
        """
        Update nested JSON object or array
        Example: set_nested(payload, "New Street", "user", "address", "street")
        """
        payload_copy = deepcopy(payload)
        current = payload_copy
        for key in keys[:-1]:
            if isinstance(current, dict) and isinstance(key, str):
                current = current.setdefault(key, {})
            elif isinstance(current, list) and isinstance(key, int):
                while len(current) <= key:
                    current.append({})
                current = current[key]
            else:
                raise KeyError(f"Cannot access key {key} in {type(current)}")
        last_key = keys[-1]
        if isinstance(current, dict) and isinstance(last_key, str):
            current[last_key] = value
        elif isinstance(current, list) and isinstance(last_key, int):
            while len(current) <= last_key:
                current.append(None)
            current[last_key] = value
        else:
            raise KeyError(f"Cannot set key {last_key} in {type(current)}")
        return payload_copy

    # ---------------- Return JSON as string ----------------
    def to_json_string(self, payload: Union[dict, list], indent: int = 4) -> str:
        return json.dumps(payload, indent=indent)

    # ---------------- Save JSON to file ----------------
    def save_json(self, payload: Union[dict, list], filename: str) -> None:
        path = Path(self.base_dir) / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

