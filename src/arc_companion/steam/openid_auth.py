"""Steam OpenID 2.0 sign-in for a desktop app: a loopback-only local HTTP
server catches the browser redirect, and the response is verified by
POSTing it back to Steam (the OpenID 2.0 anti-forgery check) before trusting
the SteamID64 it contains.

Confirmed via Valve's own docs (see the Phase 3 plan) that this is the
correct mechanism for an unofficial third-party tool — Steam's newer OAuth
is gated behind direct Valve partner approval and doesn't apply here.
"""

import http.server
import threading
import time
import urllib.parse
import webbrowser
from collections.abc import Callable

import requests

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 17823
CALLBACK_PATH = "/steam_callback"
LOGIN_TIMEOUT_SECONDS = 180

_OPENID_NS = "http://specs.openid.net/auth/2.0"
_IDENTIFIER_SELECT = "http://specs.openid.net/auth/2.0/identifier_select"


def _realm() -> str:
    return f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/"


def _return_to() -> str:
    return f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"


def build_login_url(return_to: str) -> str:
    params = {
        "openid.ns": _OPENID_NS,
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": _realm(),
        "openid.identity": _IDENTIFIER_SELECT,
        "openid.claimed_id": _IDENTIFIER_SELECT,
    }
    return f"{STEAM_OPENID_URL}?{urllib.parse.urlencode(params)}"


def verify_openid_response(params: dict[str, str]) -> str | None:
    """Re-POSTs the callback params back to Steam (the OpenID 2.0
    anti-forgery check) and, if genuine, extracts the SteamID64 from
    openid.claimed_id. Returns None on any failure — forged/invalid
    response, network error, or an unexpected claimed_id shape."""
    verify_params = dict(params)
    verify_params["openid.mode"] = "check_authentication"
    try:
        response = requests.post(STEAM_OPENID_URL, data=verify_params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    if "is_valid:true" not in response.text:
        return None

    claimed_id = params.get("openid.claimed_id", "")
    steam_id = claimed_id.rsplit("/", 1)[-1]
    return steam_id if steam_id.isdigit() else None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        self.server.received_params = params

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>Signed in! You can close this window and return to the app.</body></html>")

        self.server.received_event.set()

    def log_message(self, format_str: str, *args) -> None:
        pass  # silence default request logging to stderr


def login(
    on_complete: Callable[[str | None, dict[str, str] | None], None],
    verify_locally: bool = True,
) -> Callable[[], None]:
    """Starts the local callback server + opens the browser on a background
    thread, and calls on_complete(steam_id_or_None, raw_params_or_None) from
    that thread once a result is available (success, timeout, port
    unavailable, or explicit cancel). Returns a cancel() function the caller
    can invoke to abort early (e.g. a dialog's Cancel button).

    verify_locally=False skips the local check_authentication call and
    hands back the raw, never-verified params instead of a steam_id.
    Steam's check_authentication appears to be single-use per assertion --
    consolidate_steam_profiles() originally reused a login that had already
    been verified locally by this same function, and the server's own
    independent re-check of that already-consumed assertion was rejected
    every time (surfaced as openid_verification_failed). Any caller that
    needs to prove a login to a server itself must get its own dedicated,
    never-locally-verified login instead of reusing one that already went
    through the branch below.

    Runs entirely off the Tk thread — never touches Tk objects. Callers that
    need to update UI from on_complete must hop back onto the Tk thread
    themselves (e.g. widget.after(0, ...))."""
    try:
        server = http.server.HTTPServer((CALLBACK_HOST, CALLBACK_PORT), _CallbackHandler)
    except OSError:
        # Most likely the port's already in use by something else.
        on_complete(None, None)
        return lambda: None

    server.received_params = None
    server.received_event = threading.Event()
    cancelled = threading.Event()

    def worker() -> None:
        server.timeout = 1.0  # poll interval, so `cancelled` gets checked promptly
        webbrowser.open(build_login_url(_return_to()))
        deadline = time.monotonic() + LOGIN_TIMEOUT_SECONDS
        while (
            not server.received_event.is_set()
            and not cancelled.is_set()
            and time.monotonic() < deadline
        ):
            server.handle_request()
        server.server_close()

        if not server.received_event.is_set():
            on_complete(None, None)
            return
        if not verify_locally:
            on_complete(None, server.received_params)
            return
        steam_id = verify_openid_response(server.received_params)
        on_complete(steam_id, server.received_params if steam_id else None)

    threading.Thread(target=worker, daemon=True).start()
    return cancelled.set
