"""REST API client for Toyota Control Center backend."""

import requests
from typing import Optional, Dict, Any
from .config import ConfigManager


class RestClient:
    """API client for communicating with Toyota Control Center backend."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url or ConfigManager.get_backend_url()
        self.token = token or ConfigManager.get_token()

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self, email: str) -> dict:
        """Login with email and get access token."""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()

    def get_jobs(self, q: str = None, status: str = None, page: int = 1, page_size: int = 50) -> dict:
        """List all jobs with optional filtering."""
        params = {"page": page, "page_size": page_size}
        if q:
            params["q"] = q
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/jobs",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_job(self, job_id: str) -> dict:
        """Get a specific job by ID."""
        response = requests.get(
            f"{self.base_url}/jobs/{job_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def create_job(self, name: str, job_type: str = None, connector: str = None, config: dict = None) -> dict:
        """Create a new job."""
        payload = {
            "name": name,
            "kind": "runtime",
            "environment": "dev",
            "data_sensitivity": "low",
        }
        
        # Add type and connector if provided
        if job_type:
            payload["type"] = job_type
        if connector:
            payload["connector"] = connector
        
        # Add config as a nested field
        if config:
            payload["config"] = config
        
        response = requests.post(
            f"{self.base_url}/jobs",
            json=payload,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def update_job(self, job_id: str, config: dict) -> dict:
        """Update an existing job."""
        response = requests.patch(
            f"{self.base_url}/jobs/{job_id}",
            json=config,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        response = requests.delete(
            f"{self.base_url}/jobs/{job_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.status_code == 204

    def run_job(self, job_id: str, action: str = "default", params: dict = None) -> dict:
        """Execute a job."""
        payload = {"action": action}
        if params:
            payload["params"] = params
        
        response = requests.post(
            f"{self.base_url}/jobs/{job_id}/runs",
            json=payload,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_runs(self, job_id: str = None, status: str = None, limit: int = 200) -> dict:
        """List job runs with optional filtering."""
        params = {"limit": limit}
        if job_id:
            params["job_id"] = job_id
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/runs",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_run(self, run_id: str) -> dict:
        """Get a specific run by ID."""
        response = requests.get(
            f"{self.base_url}/runs/{run_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    # ========================================================================
    # ADMIN METHODS
    # ========================================================================

    def admin_list_users(self) -> dict:
        """Get list of users in admin's department."""
        response = requests.get(
            f"{self.base_url}/admin/users",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_list_jobs(self, status: str = None) -> dict:
        """Get list of jobs in admin's department."""
        params = {}
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/admin/jobs",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_list_high_risk_jobs(self) -> dict:
        """Get list of high-risk jobs in admin's department."""
        response = requests.get(
            f"{self.base_url}/admin/jobs/high-risk",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_list_failed_jobs(self) -> dict:
        """Get list of failed jobs in admin's department."""
        response = requests.get(
            f"{self.base_url}/admin/jobs/failed",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_list_runs(self, status: str = None, limit: int = 50) -> dict:
        """Get list of runs for department jobs."""
        params = {"limit": limit}
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/admin/runs",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_list_failed_runs(self, limit: int = 50) -> dict:
        """Get list of failed runs for department jobs."""
        params = {"limit": limit}
        
        response = requests.get(
            f"{self.base_url}/admin/runs/failed",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_list_approvals(self) -> dict:
        """Get list of pending approval requests in department."""
        response = requests.get(
            f"{self.base_url}/admin/approvals",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_approve(self, approval_id: str, comment: str = "") -> dict:
        """Approve a promotion request."""
        params = {}
        if comment:
            params["comment"] = comment
        
        response = requests.patch(
            f"{self.base_url}/admin/approvals/{approval_id}/approve",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def admin_reject(self, approval_id: str, comment: str = "") -> dict:
        """Reject a promotion request."""
        params = {}
        if comment:
            params["comment"] = comment
        
        response = requests.patch(
            f"{self.base_url}/admin/approvals/{approval_id}/reject",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()
