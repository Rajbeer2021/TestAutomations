import requests
import json
from typing import Dict, Any, Optional
from utils.logger import get_logger

class APIUtils:
    def __init__(self, base_url: str = "", default_headers: Optional[Dict[str, str]] = None, reporter=None):
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {"Content-Type": "application/json"}
        self.logger = get_logger(name="APIUtils", log_file="reports/logs/api.log")
        self.reporter = reporter  # optional reporter

    # ------------------- Internal Helpers -------------------
    def _full_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _log_request(self, method: str, url: str, headers: Dict[str, str], payload: Any):
        self.logger.info(f"API Request - {method} {url}")
        self.logger.info(f"Headers: {headers}")
        if payload:
            self.logger.info(f"Payload: {json.dumps(payload, indent=2)}")

    def _log_response(self, response: requests.Response):
        self.logger.info(f"Response Status: {response.status_code}")
        try:
            self.logger.info(f"Response Body: {json.dumps(response.json(), indent=2)}")
        except json.JSONDecodeError:
            self.logger.info(f"Response Text: {response.text}")

    # ------------------- HTTP Methods -------------------
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> requests.Response:
        url = self._full_url(endpoint)
        merged_headers = {**self.default_headers, **(headers or {})}
        self._log_request("GET", url, merged_headers, params)
        response = requests.get(url, headers=merged_headers, params=params, timeout=timeout)
        self._log_response(response)
        return response

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> requests.Response:
        url = self._full_url(endpoint)
        merged_headers = {**self.default_headers, **(headers or {})}
        self._log_request("POST", url, merged_headers, data)
        response = requests.post(url, headers=merged_headers, json=data, timeout=timeout)
        self._log_response(response)
        return response

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> requests.Response:
        url = self._full_url(endpoint)
        merged_headers = {**self.default_headers, **(headers or {})}
        self._log_request("PUT", url, merged_headers, data)
        response = requests.put(url, headers=merged_headers, json=data, timeout=timeout)
        self._log_response(response)
        return response

    def patch(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> requests.Response:
        url = self._full_url(endpoint)
        merged_headers = {**self.default_headers, **(headers or {})}
        self._log_request("PATCH", url, merged_headers, data)
        response = requests.patch(url, headers=merged_headers, json=data, timeout=timeout)
        self._log_response(response)
        return response

    def delete(self, endpoint: str, headers: Optional[Dict[str, str]] = None,
               timeout: int = 30) -> requests.Response:
        url = self._full_url(endpoint)
        merged_headers = {**self.default_headers, **(headers or {})}
        self._log_request("DELETE", url, merged_headers, None)
        response = requests.delete(url, headers=merged_headers, timeout=timeout)
        self._log_response(response)
        return response

    # ------------------- API Assertions -------------------
    def _assert(self, condition: bool, message: str):
        if not condition:
            raise AssertionError(message)

    def assert_status_code(self, response: requests.Response, expected_code: int, step_name="Assert Status Code"):
        self.logger.info(f"{step_name}: Expected={expected_code}, Actual={response.status_code}")
        self._assert(response.status_code == expected_code,
                     f"{step_name} Failed! Expected {expected_code}, got {response.status_code}")

    def assert_json_key_exists(self, response_json: dict, key: str, step_name="Assert JSON Key Exists"):
        self._assert(key in response_json, f"{step_name} Failed! Key '{key}' not found in response JSON")

    def assert_json_key_not_exists(self, response_json: dict, key: str, step_name="Assert JSON Key Not Exists"):
        self._assert(key not in response_json, f"{step_name} Failed! Key '{key}' should NOT exist in response JSON")

    def assert_json_value(self, response_json: dict, key: str, expected_value, step_name="Assert JSON Value"):
        actual = response_json.get(key)
        self._assert(actual == expected_value,
                     f"{step_name} Failed! Key '{key}': Expected '{expected_value}', got '{actual}'")

    def assert_json_contains(self, response_json: dict, expected_subset: dict, step_name="Assert JSON Contains"):
        for k, v in expected_subset.items():
            self._assert(response_json.get(k) == v,
                         f"{step_name} Failed! Expected key '{k}'='{v}', got '{response_json.get(k)}'")

    def assert_json_matches(self, response_json: dict, expected_json: dict, step_name="Assert JSON Match"):
        """Exact JSON match"""
        self._assert(response_json == expected_json,
                     f"{step_name} Failed! Expected JSON: {expected_json}, Got: {response_json}")

    def assert_response_contains_text(self, response: requests.Response, expected_text: str,
                                      step_name="Assert Response Contains Text"):
        self._assert(expected_text in response.text,
                     f"{step_name} Failed! Expected text '{expected_text}' not found in response body")

    def assert_json_path_value(self, response_json: dict, json_path: str, expected_value,
                               step_name="Assert JSON Path Value"):
        """
        JSON path support (simple dot notation)
        e.g., "data.user.name"
        """
        keys = json_path.split(".")
        val = response_json
        try:
            for key in keys:
                val = val[key]
        except (KeyError, TypeError):
            raise AssertionError(f"{step_name} Failed! JSON path '{json_path}' not found")
        self._assert(val == expected_value,
                     f"{step_name} Failed! Expected '{expected_value}', got '{val}'")

    # ------------------- Array / List Assertions -------------------

    def assert_array_length(self, response_json: dict, json_path: str, expected_length: int,
                            step_name="Assert Array Length"):
        """
        Assert the length of an array at a given JSON path
        e.g., json_path = "data.items"
        """
        arr = self._get_json_path_value(response_json, json_path)
        self._assert(isinstance(arr, list), f"{step_name} Failed! Path '{json_path}' is not an array")
        self._assert(len(arr) == expected_length,
                     f"{step_name} Failed! Expected length {expected_length}, got {len(arr)}")

    def assert_array_contains(self, response_json: dict, json_path: str, expected_value,
                              step_name="Assert Array Contains"):
        """
        Assert that an array contains a value
        """
        arr = self._get_json_path_value(response_json, json_path)
        self._assert(isinstance(arr, list), f"{step_name} Failed! Path '{json_path}' is not an array")
        self._assert(expected_value in arr,
                     f"{step_name} Failed! Value '{expected_value}' not found in array at '{json_path}'")

    def assert_array_of_dicts_contains(self, response_json: dict, json_path: str, expected_dict: dict,
                                       step_name="Assert Array of Dicts Contains"):
        """
        Assert that an array of objects contains a dict matching the subset
        """
        arr = self._get_json_path_value(response_json, json_path)
        self._assert(isinstance(arr, list), f"{step_name} Failed! Path '{json_path}' is not an array")
        found = False
        for item in arr:
            if isinstance(item, dict) and all(item.get(k) == v for k, v in expected_dict.items()):
                found = True
                break
        self._assert(found, f"{step_name} Failed! No dict matching {expected_dict} found in array at '{json_path}'")

    # ------------------- Private Helper -------------------
    def _get_json_path_value(self, response_json: dict, json_path: str):
        """Retrieve value from JSON using dot notation path"""
        keys = json_path.split(".")
        val = response_json
        try:
            for key in keys:
                val = val[key]
        except (KeyError, TypeError):
            raise AssertionError(f"JSON path '{json_path}' not found")
        return val
