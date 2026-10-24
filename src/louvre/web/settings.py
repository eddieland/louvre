"""What a deployment is configured with, read from its environment once, when the app is built (docs/DEPLOY.md).

Nothing here is a secret kept in code: the GitHub app's secret is read from the environment, and only its presence is
ever shown.
"""

import os
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Self

from louvre.core import db
from louvre.core.maps import streets


@dataclass(frozen=True)
class Settings:
    """A deployment's configuration."""

    #: The Postgres database, or None when none is configured: the app then serves its pages and says so.
    database_url: str | None
    #: Where Louvre's pages are, such as `https://louvre.example.com`, for the links a publish returns; empty to use
    #: the address each request came to.
    base_url: str
    #: The GitHub OAuth app people sign in with; both empty when GitHub sign-in is off.
    github_client_id: str
    github_client_secret: str
    #: The GitHub logins allowed to sign in, lowercase; `*` in it lets anyone with a GitHub account in.
    allowed_logins: AbstractSet[str]
    #: Whether anyone may sign in as anyone by typing a name: for a local run, tests, and a throwaway preview only.
    dev_sign_in: bool
    #: Whether the demo's artifacts are published, and readable without signing in.
    demo: bool
    #: Whether the session cookie is sent over HTTPS only.
    secure_cookies: bool
    #: The TileJSON of the street tiles Louvre passes on to a map (louvre.core.maps.streets); empty for none.
    streets: str = streets.OPENFREEMAP

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> Self:
        """Read the configuration from `environ`, this process's environment unless given.

        Returns:
            The settings.
        """
        env = os.environ if environ is None else environ
        allowed = {login.strip().lower() for login in env.get("LOUVRE_ALLOWED_LOGINS", "").split(",")}
        return cls(
            database_url=db.url_from(env),
            base_url=env.get("LOUVRE_BASE_URL", "").rstrip("/"),
            github_client_id=env.get("LOUVRE_GITHUB_CLIENT_ID", ""),
            github_client_secret=env.get("LOUVRE_GITHUB_CLIENT_SECRET", ""),
            allowed_logins=frozenset(allowed - {""}),
            dev_sign_in=_flag(env, "LOUVRE_DEV_SIGN_IN"),
            demo=_flag(env, "LOUVRE_DEMO"),
            # Vercel serves only HTTPS; a local run is plain HTTP.
            secure_cookies=bool(env.get("VERCEL")) or _flag(env, "LOUVRE_SECURE_COOKIES"),
            streets=env.get("LOUVRE_STREETS", streets.OPENFREEMAP).strip(),
        )

    @property
    def github(self) -> bool:
        """Whether people can sign in with GitHub."""
        return bool(self.github_client_id and self.github_client_secret)

    def allows(self, login: str) -> bool:
        """Say whether the GitHub login `login` may sign in.

        Returns:
            True when it is on the allowlist, or the allowlist lets anyone in.
        """
        return "*" in self.allowed_logins or login.lower() in self.allowed_logins


def _flag(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
