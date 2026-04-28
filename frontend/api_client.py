import requests
from typing import Any
from dotenv import load_dotenv
import os

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


class APIClient:
    """
    Thin wrapper around requests for our FastAPI backend.
    Handles auth headers, error parsing, and response formatting.
    """

    def __init__(self):
        self.base_url = API_BASE_URL
        self.token: str | None = None
        self.session = requests.Session()

    def set_token(self, token: str) -> None:
        """Store JWT token — attached to all future requests."""
        self.token = token
        self.session.headers.update({
            "Authorization": f"Bearer {token}"
        })

    def clear_token(self) -> None:
        """Clear token on logout."""
        self.token = None
        self.session.headers.pop("Authorization", None)

    def _handle_response(self, response: requests.Response) -> dict:
        """
        Standardized response handler.
        Returns dict with success/error info always.
        Never raises — UI should always get a response to show.
        """
        try:
            data = response.json()
        except Exception:
            data = {"detail": response.text}

        if response.status_code == 200:
            return {"success": True, "data": data}
        elif response.status_code == 401:
            return {"success": False, "error": "Invalid credentials or session expired"}
        elif response.status_code == 403:
            return {"success": False, "error": "Access denied for your role"}
        elif response.status_code == 400:
            return {"success": False, "error": data.get("detail", "Bad request")}
        else:
            return {
                "success": False,
                "error": data.get("detail", f"Error {response.status_code}")
            }

    def login(self, username: str, password: str) -> dict:
        """
        POST /auth/login — OAuth2 form data login.
        Returns token + role info on success.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data={
                    "username": username,
                    "password": password
                },
                timeout=10
            )
            result = self._handle_response(response)

            if result["success"]:
                token = result["data"]["access_token"]
                self.set_token(token)

            return result

        except requests.ConnectionError:
            return {
                "success": False,
                "error": "Cannot connect to API. Is the FastAPI server running?"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def query(self, question: str) -> dict:
        """
        POST /query/ — Submit natural language question.
        Returns answer + SQL + metrics.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/query/",
                json={"question": question},
                timeout=60  
            )
            return self._handle_response(response)

        except requests.Timeout:
            return {
                "success": False,
                "error": "Request timed out — the pipeline took too long. Try again."
            }
        except requests.ConnectionError:
            return {
                "success": False,
                "error": "Lost connection to API server."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_history(self, limit: int = 10) -> dict:
        """GET /query/history — Fetch recent query history."""
        try:
            response = self.session.get(
                f"{self.base_url}/query/history",
                params={"limit": limit},
                timeout=10
            )
            return self._handle_response(response)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def health_check(self) -> dict:
        """GET /health — Check if API is reachable."""
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return self._handle_response(response)
        except Exception:
            return {"success": False, "error": "API unreachable"}


api_client = APIClient()