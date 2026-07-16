import urllib.parse

import pytest
import requests

from arc_companion.steam import openid_auth


def test_build_login_url_has_required_openid_params():
    url = openid_auth.build_login_url("http://127.0.0.1:17823/steam_callback")
    parsed = urllib.parse.urlparse(url)
    assert parsed.netloc == "steamcommunity.com"
    params = urllib.parse.parse_qs(parsed.query)
    assert params["openid.ns"] == ["http://specs.openid.net/auth/2.0"]
    assert params["openid.mode"] == ["checkid_setup"]
    assert params["openid.return_to"] == ["http://127.0.0.1:17823/steam_callback"]
    assert "openid.realm" in params
    assert "openid.identity" in params
    assert "openid.claimed_id" in params


class _FakeResponse:
    def __init__(self, text: str, ok: bool = True):
        self.text = text
        self._ok = ok

    def raise_for_status(self) -> None:
        if not self._ok:
            raise requests.HTTPError("boom")


def test_verify_openid_response_accepts_valid_assertion(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FakeResponse("ns:...\nis_valid:true\n"))
    params = {
        "openid.claimed_id": "https://steamcommunity.com/openid/id/76561198012345678",
        "openid.sig": "fake",
        "openid.signed": "fake",
    }
    assert openid_auth.verify_openid_response(params) == "76561198012345678"


def test_verify_openid_response_rejects_invalid_assertion(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FakeResponse("is_valid:false\n"))
    params = {"openid.claimed_id": "https://steamcommunity.com/openid/id/76561198012345678"}
    assert openid_auth.verify_openid_response(params) is None


def test_verify_openid_response_handles_network_failure(monkeypatch):
    def boom(*a, **kw):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(requests, "post", boom)
    params = {"openid.claimed_id": "https://steamcommunity.com/openid/id/76561198012345678"}
    assert openid_auth.verify_openid_response(params) is None


def test_verify_openid_response_rejects_malformed_claimed_id(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FakeResponse("is_valid:true\n"))
    params = {"openid.claimed_id": "https://steamcommunity.com/openid/id/not-a-steamid"}
    assert openid_auth.verify_openid_response(params) is None


def test_verify_openid_response_handles_http_error_status(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FakeResponse("", ok=False))
    params = {"openid.claimed_id": "https://steamcommunity.com/openid/id/76561198012345678"}
    assert openid_auth.verify_openid_response(params) is None
