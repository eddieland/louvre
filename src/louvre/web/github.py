"""Signing in with GitHub: OAuth's web flow, as GitHub documents it, with two calls of the stdlib's own.

GitHub sends the person back with a code; Louvre trades it for a token, asks GitHub who the token is for, and forgets
the token. The account id is GitHub's numeric user id, which a renamed login keeps.
"""

import json
import urllib.parse
import urllib.request
from typing import cast

from louvre.core.accounts import Account

#: Where a person is sent to approve Louvre.
AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
#: Where a code is traded for a token, and where the token's person is read.
TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105  (a URL, not a secret)
USER_URL = "https://api.github.com/user"
#: How long either call may take, in seconds.
TIMEOUT = 10


class SignInError(Exception):
    """GitHub did not say who signed in."""


def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Make the URL that asks the person to approve Louvre, which reads only their public profile.

    Returns:
        The URL.
    """
    query = urllib.parse.urlencode(
        {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "allow_signup": "false"},
    )
    return f"{AUTHORIZE_URL}?{query}"


def account_for(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Account:
    """Find who signed in, from the code GitHub sent them back with.

    Returns:
        Their account, as `gh:ID`.

    Raises:
        SignInError: GitHub refused the code, or did not say who it is for.
    """
    answer = _post_json(
        TOKEN_URL,
        {"client_id": client_id, "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri},
    )
    token = answer.get("access_token")
    if not isinstance(token, str) or not token:
        raise SignInError(str(answer.get("error_description") or "GitHub refused the sign-in"))
    user = _get_json(USER_URL, token)
    user_id, login, name = user.get("id"), user.get("login"), user.get("name")
    if not isinstance(user_id, int) or not isinstance(login, str):
        raise SignInError("GitHub did not say who signed in")
    return Account(f"gh:{user_id}", login, name if isinstance(name, str) and name.strip() else login)


def _post_json(url: str, form: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(  # noqa: S310  (a constant https URL)
        url,
        data=urllib.parse.urlencode(form).encode(),
        headers={"Accept": "application/json"},
        method="POST",
    )
    return _send(request)


def _get_json(url: str, token: str) -> dict[str, object]:
    request = urllib.request.Request(  # noqa: S310  (a constant https URL)
        url,
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"},
    )
    return _send(request)


def _send(request: urllib.request.Request) -> dict[str, object]:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310  (as above)
            found: object = json.load(response)
    except (OSError, ValueError) as e:
        raise SignInError(f"GitHub could not be reached: {type(e).__name__}") from None
    if not isinstance(found, dict):
        raise SignInError("GitHub answered with something other than an object")
    return cast("dict[str, object]", found)
