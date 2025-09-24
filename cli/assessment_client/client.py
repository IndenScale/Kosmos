"""
Client for interacting with the Kosmos Assessment Service API.
"""
import requests
import json
import sys
import os
from urllib.parse import urljoin

# --- Global Configuration ---
ASSESSMENT_API_BASE_URL = os.getenv("KOSMOS_ASSESSMENT_API_URL", "http://127.0.0.1:8015/api/v1/")

def _handle_api_error(e: requests.exceptions.RequestException):
    """Unified API error handler for the assessment service."""
    print(f"错误: 评估服务API请求失败 - {e}", file=sys.stderr)
    if e.response is not None:
        try:
            response_data = e.response.json()
            if isinstance(response_data, dict):
                detail = response_data.get("detail", e.response.text)
            else:
                detail = str(response_data)
            print(f"响应 ({e.response.status_code}): {detail}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"响应 ({e.response.status_code}): {e.response.text}", file=sys.stderr)
    sys.exit(1)

class AssessmentClient:
    """A stateful client for interacting with the Kosmos Assessment Service API."""

    def __init__(self, token: str):
        if not token:
            print("错误: AssessmentClient 必须使用一个有效的认证token进行初始化。", file=sys.stderr)
            sys.exit(1)
        self._session = requests.Session()
        self._access_token = token

    def _get_auth_header(self):
        """Returns the authorization header."""
        return {"Authorization": f"Bearer {self._access_token}"}

    def _request(self, method, endpoint, **kwargs):
        """Generic wrapper for making authenticated requests."""
        url = urljoin(ASSESSMENT_API_BASE_URL, endpoint)
        headers = self._get_auth_header()
        if 'json' in kwargs:
            headers['Content-Type'] = 'application/json'
        
        try:
            response = self._session.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.status_code != 204 else None
        except requests.exceptions.RequestException as e:
            _handle_api_error(e)

    # --- Framework Management Methods ---

    def list_frameworks(self, skip: int = 0, limit: int = 100):
        """Lists all assessment frameworks."""
        params = {"skip": skip, "limit": limit}
        return self._request("GET", "frameworks/", params=params)

    def create_framework(self, name: str, version: str, description: str = None, source: str = None):
        """Creates a new assessment framework."""
        payload = {
            "name": name,
            "version": version,
            "description": description,
            "source": source
        }
        # Filter out None values
        valid_payload = {k: v for k, v in payload.items() if v is not None}
        return self._request("POST", "frameworks/", json=valid_payload)

    def get_framework(self, framework_id: str):
        """Retrieves a specific framework by its ID."""
        return self._request("GET", f"frameworks/{framework_id}")

    def delete_framework(self, framework_id: str):
        """Deletes a specific framework by its ID."""
        return self._request("DELETE", f"frameworks/{framework_id}")

    def import_control_items(self, framework_id: str, file_path: str):
        """Bulk imports control items from a JSONL file."""
        endpoint = f"frameworks/{framework_id}/control_items/import"
        url = urljoin(ASSESSMENT_API_BASE_URL, endpoint)
        headers = self._get_auth_header()

        if not os.path.exists(file_path):
            print(f"错误: 文件未找到 '{file_path}'", file=sys.stderr)
            sys.exit(1)

        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/jsonl')}
            try:
                response = self._session.post(url, headers=headers, files=files)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                _handle_api_error(e)

    # --- Job Management Methods ---

    def list_jobs(self, skip: int = 0, limit: int = 100):
        """Lists all assessment jobs."""
        params = {"skip": skip, "limit": limit}
        return self._request("GET", "jobs/", params=params)

    def create_job(self, name: str, framework_id: str, ks_id: str):
        """Creates a new assessment job."""
        payload = {
            "name": name,
            "framework_id": framework_id,
            "knowledge_spaces": [
                {"ks_id": ks_id, "role": "target"}
            ]
        }
        return self._request("POST", "jobs/", json=payload)

    def get_job(self, job_id: str):
        """Retrieves a specific job by its ID."""
        return self._request("GET", f"jobs/{job_id}")

    def delete_jobs(self, job_ids: list):
        """Deletes one or more jobs by their IDs."""
        payload = {"job_ids": job_ids}
        return self._request("DELETE", "jobs/", json=payload)

    def execute_job(self, job_id: str, payload: dict):
        """
        Executes a job with a given configuration payload.
        """
        return self._request("POST", f"execute/job/{job_id}", json=payload)
        
    def requeue_job(self, job_id: str, payload: dict):
        """
        Requeues a job with a given configuration payload.
        """
        return self._request("POST", f"execute/job/{job_id}/requeue", json=payload)

    def list_sessions(self, job_id: str = None, status: str = None, skip: int = 0, limit: int = 100):
        """
        Lists sessions with optional filters for job_id and status.
        """
        params = {"skip": skip, "limit": limit}
        if job_id:
            params["job_id"] = job_id
        if status:
            params["status"] = status
        
        return self._request("GET", "sessions/", params=params)

    def get_session(self, session_id: str):
        """
        Get details of a single assessment session by its ID.
        """
        return self._request("GET", f"sessions/{session_id}")

    def execute_session(self, payload: dict):
        """Executes a single session with a given configuration payload."""
        return self._request("POST", "execute/session", json=payload)

    # --- Finding Management Methods ---

    def list_findings(self, finding_ids: list = None, session_id: str = None, job_id: str = None, judgements: list = None):
        """Lists assessment findings with optional filtering."""
        params = {}
        if finding_ids:
            params['finding_ids'] = finding_ids
        if session_id:
            params['session_id'] = session_id
        if job_id:
            params['job_id'] = job_id
        if judgements:
            params['judgements'] = judgements
        return self._request("GET", "findings/", params=params)

    def get_finding(self, finding_id: str):
        """Retrieves a specific finding by its ID."""
        return self._request("GET", f"findings/{finding_id}")
