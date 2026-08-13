import random
import string
import uuid
import time
from datetime import datetime
from typing import Any, List, Tuple, Set, Dict, Union
import json

class TestDataUtils:
    """
    Comprehensive utility functions for hybrid automation testing:
    - Random strings, numbers, emails, passwords, UUIDs
    - Random JSON payloads
    - Random data structures: list, tuple, set, dict
    - Timestamps and sleeps
    """

    # ---------------- Basic Random Generators ----------------

    @staticmethod
    def random_string(length: int = 8, chars: str = string.ascii_letters) -> str:
        return ''.join(random.choice(chars) for _ in range(length))

    @staticmethod
    def random_number(length: int = 6) -> str:
        return ''.join(random.choice(string.digits) for _ in range(length))

    @staticmethod
    def random_email(domain: str = "example.com") -> str:
        return f"{TestDataUtils.random_string(6)}@{domain}"

    @staticmethod
    def random_password(length: int = 12, use_special: bool = True) -> str:
        chars = string.ascii_letters + string.digits
        if use_special:
            chars += "!@#$%^&*()-_=+[]{}|;:,.<>/?"
        return ''.join(random.choice(chars) for _ in range(length))

    @staticmethod
    def generate_uuid() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def timestamp(format_str: str = "%Y%m%d%H%M%S") -> str:
        return datetime.now().strftime(format_str)

    @staticmethod
    def random_boolean() -> bool:
        return bool(random.getrandbits(1))

    @staticmethod
    def random_float(min_value: float = 0, max_value: float = 100, precision: int = 2) -> float:
        return round(random.uniform(min_value, max_value), precision)

    @staticmethod
    def sleep_random(min_seconds: int = 1, max_seconds: int = 5) -> float:
        duration = random.uniform(min_seconds, max_seconds)
        time.sleep(duration)
        return duration

    # ---------------- Random Collections ----------------

    @staticmethod
    def random_list(size: int = 5, item_type: Any = str) -> List:
        if item_type == str:
            return [TestDataUtils.random_string(6) for _ in range(size)]
        elif item_type == int:
            return [random.randint(0, 1000) for _ in range(size)]
        elif item_type == float:
            return [TestDataUtils.random_float() for _ in range(size)]
        elif item_type == bool:
            return [TestDataUtils.random_boolean() for _ in range(size)]
        else:
            return [None for _ in range(size)]

    @staticmethod
    def random_tuple(size: int = 5, item_type: Any = str) -> Tuple:
        return tuple(TestDataUtils.random_list(size, item_type))

    @staticmethod
    def random_set(size: int = 5, item_type: Any = str) -> Set:
        return set(TestDataUtils.random_list(size, item_type))

    @staticmethod
    def random_dict(keys: List[str] = None, value_type: Any = str) -> Dict:
        if keys is None:
            keys = [TestDataUtils.random_string(5) for _ in range(5)]
        return {key: TestDataUtils.random_list(1, value_type)[0] for key in keys}

    # ---------------- Random JSON / Payload Builders ----------------

    @staticmethod
    def random_json_object(depth: int = 1, keys_per_level: int = 3) -> dict:
        """
        Generates a nested random JSON object.
        - depth: levels of nested objects
        - keys_per_level: number of keys per object
        """
        obj = {}
        for _ in range(keys_per_level):
            key = TestDataUtils.random_string(5)
            if depth > 1:
                obj[key] = TestDataUtils.random_json_object(depth - 1, keys_per_level)
            else:
                choice = random.choice(['string', 'int', 'float', 'bool', 'list'])
                if choice == 'string':
                    obj[key] = TestDataUtils.random_string(6)
                elif choice == 'int':
                    obj[key] = random.randint(0, 1000)
                elif choice == 'float':
                    obj[key] = TestDataUtils.random_float()
                elif choice == 'bool':
                    obj[key] = TestDataUtils.random_boolean()
                elif choice == 'list':
                    obj[key] = TestDataUtils.random_list(random.randint(1, 5))
        return obj

    @staticmethod
    def json_from_file(file_path: str, child_objects: List[str] = None) -> Union[dict, list]:
        """
        Load JSON file and optionally return nested child object(s)
        """
        with open(file_path, "r") as f:
            data = json.load(f)
        if child_objects:
            for child in child_objects:
                data = data.get(child, {})
        return data

    @staticmethod
    def update_json_value(json_obj: dict, keys: List[str], value: Any) -> dict:
        """
        Update nested JSON object by a list of keys.
        keys = ['parent', 'child', 'subchild']
        """
        obj = json_obj
        for key in keys[:-1]:
            obj = obj.setdefault(key, {})
        obj[keys[-1]] = value
        return json_obj

    @staticmethod
    def set_random_values_in_json(json_obj: dict, key_types: dict) -> dict:
        """
        Automatically set random values in a JSON object based on key types.
        key_types example: {'username': 'string', 'id': 'int', 'isActive': 'bool'}
        """
        for k, t in key_types.items():
            if t == 'string':
                json_obj[k] = TestDataUtils.random_string(8)
            elif t == 'int':
                json_obj[k] = random.randint(0, 1000)
            elif t == 'float':
                json_obj[k] = TestDataUtils.random_float()
            elif t == 'bool':
                json_obj[k] = TestDataUtils.random_boolean()
            elif t == 'uuid':
                json_obj[k] = TestDataUtils.generate_uuid()
            elif t == 'email':
                json_obj[k] = TestDataUtils.random_email()
        return json_obj
