import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional

from .task_models import HeavyProcessTask


log = logging.getLogger(__name__)


class TaskClientError(RuntimeError):
    pass


class TaskClient:
    def fetch_next_task(self, task_type: str) -> Optional[HeavyProcessTask]:
        raise NotImplementedError

    def complete_task(self, task_id: str, payload: Dict) -> None:
        raise NotImplementedError


class HttpTaskClient(TaskClient):
    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def fetch_next_task(self, task_type: str) -> Optional[HeavyProcessTask]:
        query = urllib.parse.urlencode({"task_type": task_type})
        url = f"{self.base_url}/tasks/next?{query}"
        status, payload = self._request("GET", url)
        if status == 204 or payload is None:
            return None
        try:
            return HeavyProcessTask.from_dict(payload)
        except Exception as exc:  # noqa: BLE001
            raise TaskClientError(f"Failed to parse task payload: {payload}") from exc

    def complete_task(self, task_id: str, payload: Dict) -> None:
        url = f"{self.base_url}/tasks/{task_id}/complete"
        status, _ = self._request("POST", url, data=payload)
        if status >= 400:
            raise TaskClientError(f"Server rejected completion for task {task_id} with status {status}")

    def _request(self, method: str, url: str, data: Optional[Dict] = None):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        encoded = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url=url, data=encoded, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read()
                if not body:
                    return status, None
                return status, json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                return 204, None
            log.error("HTTP error %s for %s %s: %s", exc.code, method, url, exc.read())
            raise TaskClientError(f"HTTP error {exc.code} for {method} {url}") from exc
        except urllib.error.URLError as exc:
            raise TaskClientError(f"Network error for {method} {url}: {exc}") from exc
