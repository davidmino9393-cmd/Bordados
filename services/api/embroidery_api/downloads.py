"""Opaque short-lived grants, bound to an owner/job/artifact/hash."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets

from embroidery_contracts.results import ArtifactDownload, DOWNLOAD_TTL_SECONDS

from .errors import ApiProblem
from .store import canonical


ASSET_SCOPE = "asset"


def utc_now():
    return datetime.now(timezone.utc)


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class DownloadSigner:
    def __init__(self, secret, base_url, clock=utc_now):
        self.secret = secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.clock = clock

    def issue(self, owner, job_id, artifact):
        return self._issue({"owner": owner, "job_id": job_id, "artifact_id": artifact.artifact_id, "sha256": artifact.sha256})

    def issue_asset(self, owner, asset):
        """Descarga del original subido (misma duración y firma). `job_id` lleva el proyecto, `artifact_id` el asset."""
        return self._issue({"owner": owner, "job_id": asset.project_id, "artifact_id": asset.asset_id, "sha256": asset.sha256, "scope": ASSET_SCOPE})

    def _issue(self, grant):
        issued = self.clock().astimezone(timezone.utc)
        expires = issued + timedelta(seconds=DOWNLOAD_TTL_SECONDS)
        grant = {**grant, "expires": expires.timestamp(), "nonce": secrets.token_urlsafe(18)}
        payload = encode(canonical(grant).encode())
        signature = encode(hmac.new(self.secret, payload.encode(), hashlib.sha256).digest())
        return ArtifactDownload(url=f"{self.base_url}/downloads/{payload}.{signature}", issued_at=issued, expires_at=expires)

    def verify(self, token):
        try:
            payload, signature = token.split(".")
            expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(decode(signature), expected):
                raise ValueError("signature")
            grant = json.loads(decode(payload))
            if self.clock().timestamp() >= grant["expires"]:
                raise ValueError("expired")
            if not all(isinstance(grant.get(name), str) for name in ("owner", "job_id", "artifact_id", "sha256")):
                raise ValueError("scope")
            return grant
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise ApiProblem("FORBIDDEN", "La autorización de descarga venció o no es válida.") from None
