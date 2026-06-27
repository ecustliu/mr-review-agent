import time
from pathlib import Path
from typing import Optional

import httpx
import jwt

from app.config import Settings


class GitHubAuthError(RuntimeError):
    pass


class GitHubAppAuth:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._token: Optional[str] = None
        self._token_expires_at = 0.0

    async def installation_token(self, installation_id: Optional[int] = None) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        resolved_installation_id = installation_id or self._configured_installation_id()
        if resolved_installation_id is None:
            raise GitHubAuthError("GITHUB_INSTALLATION_ID or webhook installation.id is required")

        async with httpx.AsyncClient(base_url=self.settings.github_api_url) as client:
            response = await client.post(
                f"/app/installations/{resolved_installation_id}/access_tokens",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.app_jwt()}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()

        payload = response.json()
        self._token = payload["token"]
        # GitHub returns an ISO timestamp; the token currently lives for 1 hour.
        self._token_expires_at = time.time() + 3300
        return self._token

    def app_jwt(self) -> str:
        if not self.settings.github_app_id:
            raise GitHubAuthError("GITHUB_APP_ID is required")
        if not self.settings.github_app_private_key_path:
            raise GitHubAuthError("GITHUB_APP_PRIVATE_KEY_PATH is required")

        private_key = Path(self.settings.github_app_private_key_path).read_text(encoding="utf-8")
        now = int(time.time())
        return jwt.encode(
            {
                "iat": now - 60,
                "exp": now + 540,
                "iss": self.settings.github_app_id,
            },
            private_key,
            algorithm="RS256",
        )

    def _configured_installation_id(self) -> Optional[int]:
        if self.settings.github_installation_id is None:
            return None
        return int(self.settings.github_installation_id)
