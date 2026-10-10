"""HTTP session and downloads for FuOverflow.

All network I/O lives here; the parsers in ``fuo.parse`` stay pure.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE = "https://fuoverflow.com"
CHROME_DIR = Path.home() / "Library/Application Support/Google/Chrome"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class LoginRequired(RuntimeError):
    """FuOverflow answered a protected resource with the login page."""


def load_cookie_file(path: Path) -> dict[str, str]:
    """Read a Netscape ``cookies.txt`` (browser extension / curl format)."""
    cookies: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies


def parse_cookie_string(raw: str) -> dict[str, str]:
    """Parse a raw ``Cookie:`` header value into a name/value map."""
    cookies: dict[str, str] = {}
    for pair in raw.split(";"):
        name, sep, value = pair.strip().partition("=")
        if sep and name:
            cookies[name] = value
    return cookies


def load_cookies(raw: str | None, path: Path) -> dict[str, str]:
    """Cookies from a pasted value, else ``cookies.txt``, else the logged-in local Chrome."""
    if raw:
        return parse_cookie_string(raw) if "=" in raw else {"xf_user": raw}
    if path.exists():
        return load_cookie_file(path)
    return chrome_cookies()


def chrome_cookies() -> dict[str, str]:
    """FuOverflow cookies from the first local Chrome profile that is logged in."""
    # Imported here: only a local run reads Chrome; the hosted server never does.
    from pycookiecheat import BrowserType, get_cookies

    try:
        password = _chrome_password()
        profiles = sorted(p.name for p in CHROME_DIR.glob("*") if (p / "Cookies").exists()) or [None]
        for profile in profiles:
            cookies = get_cookies(BASE + "/", browser=BrowserType.CHROME, password=password, profile_name=profile)
            if cookies.get("xf_user"):
                return cookies
    except Exception as exc:
        raise LoginRequired(f"Không đọc được cookie từ Chrome: {exc}") from exc
    raise LoginRequired(
        "Chrome chưa đăng nhập FuOverflow. Đăng nhập fuoverflow.com trên Chrome rồi thử lại "
        "(hoặc đặt cookies.txt / dán xf_user)."
    )


def _chrome_password() -> str | None:
    """Chrome's cookie key on macOS, read with the ``security`` tool.

    pycookiecheat's own lookup goes through ``keyring``, which the Keychain refuses
    for a plain Python binary; the ``security`` tool is allowed. Other platforms
    let pycookiecheat find the key itself.
    """
    if sys.platform != "darwin":
        return None
    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage", "-a", "Chrome"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class Session:
    """Authenticated, rate-limited FuOverflow client."""

    def __init__(self, cookies: dict[str, str], *, delay: float = 0.6):
        if not cookies.get("xf_user"):
            raise LoginRequired(
                "No xf_user cookie found. FuOverflow hides exam images and media "
                "comments behind login; export cookies.txt from a logged-in browser."
            )
        self._delay = delay
        self._client = httpx.Client(
            base_url=BASE,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
                "Referer": f"{BASE}/",
            },
            cookies=cookies,
            follow_redirects=True,
            timeout=30.0,
        )

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    def get_html(self, path: str) -> str:
        response = self._request(path)
        text = response.text
        if "data-template=\"login\"" in text[:4000]:
            raise LoginRequired(f"Login page returned for {response.url}")
        return text

    def get_bytes(self, path: str) -> bytes:
        return self._request(path).content

    def _request(self, path: str) -> httpx.Response:
        time.sleep(self._delay)
        response = self._client.get(path)
        if response.status_code == 403 or "/login" in str(response.url):
            raise LoginRequired(
                f"FuOverflow refused {path}. Refresh cookies.txt from a logged-in browser."
            )
        response.raise_for_status()
        return response
