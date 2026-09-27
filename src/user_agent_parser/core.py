# User Agent Parser
"""Pattern-based parser for HTTP User-Agent header strings.

The goal is to return a small, predictable record describing the browser,
engine, operating system, and device class implied by a User-Agent string.
We do not attempt to identify every niche client ever shipped; we cover the
common modern set and degrade to `"unknown"` rather than guessing.

Design choices, stated plainly:

- Order matters. Patterns are tried in a fixed priority order. Browsers that
  spoof others (Edge spoofing Chrome, Chrome spoofing Safari) are checked
  before the spoofed target so the most specific match wins.
- A match sets only the fields its pattern is confident about. A browser
  pattern does not overwrite an OS already identified by an earlier pattern.
- Versions are the first capture group of each regex. If a pattern has no
  capture group, the version is `None`.
- Device type is inferred from OS plus a few explicit signals (iPad, mobile
  tokens). We do not try to detect phone vs. tablet for Android tablets,
  which is genuinely ambiguous from the UA alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class UserAgentResult:
    """Parsed view of a User-Agent string.

    `version` fields are strings (e.g. `"120.0.6099.130"`) or `None` when no
    version could be extracted. `device` is one of `"desktop"`, `"mobile"`,
    `"tablet"`, or `"unknown"`.
    """

    browser: str = "unknown"
    browser_version: Optional[str] = None
    engine: str = "unknown"
    engine_version: Optional[str] = None
    os: str = "unknown"
    os_version: Optional[str] = None
    device: str = "unknown"


# Each entry: (label, compiled regex). The regex MUST have exactly one capture
# group for the version, or use a group that captures the version. If a label
# does not expose a version, the regex still needs a group; we use `(\d[\d.]*)`
# and accept that it may be absent.
#
# We compile once at import time. These objects are small and reused across
# every parse call, which matters because parse() is often called in hot paths
# (request logging).


def _v(pattern: str) -> re.Pattern:
    """Compile a pattern; the first group is the version capture."""
    return re.compile(pattern, re.IGNORECASE)


# --- Browser patterns -----------------------------------------------------
# Order is significant: more specific / spoofing browsers first.
#
# Edge (Chromium) identifies itself as "Edg/<ver>". It also contains
# "Chrome" and "Safari", so it must be checked before either.
# Opera identifies as "OPR/<ver>" (Chromium-based) or "Opera/<ver>" (old).
# Samsung Internet identifies as "SamsungBrowser/<ver>".
# Firefox identifies as "Firefox/<ver>".
# Chrome identifies as "Chrome/<ver>" but also contains "Safari".
# Safari is the fallback for "Version/<ver> ... Safari".
# IE identifies as "MSIE <ver>" or "Trident/7.0; rv:11.0".

_BROWSER_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Edge", _v(r"Edg(?:e|A|iOS)?/(\d[\d.]*)")),
    ("Opera", _v(r"OPR/(\d[\d.]*)")),
    ("Opera", _v(r"Opera[/ ](\d[\d.]*)")),
    ("Samsung Internet", _v(r"SamsungBrowser/(\d[\d.]*)")),
    ("Firefox", _v(r"Firefox/(\d[\d.]*)")),
    ("Chrome", _v(r"Chrome/(\d[\d.]*)")),
    # Safari: use Version/ as the version anchor when present, else Safari/.
    ("Safari", _v(r"Version/(\d[\d.]*)")),
    ("Safari", _v(r"Safari/(\d[\d.]*)")),
    ("IE", _v(r"MSIE (\d[\d.]*)")),
    # IE 11 in some views does not emit MSIE; identify via Trident + rv.
    ("IE", _v(r"Trident/7\.0.*rv:(\d[\d.]*)")),
]


# --- Engine patterns ------------------------------------------------------
# Geck|Goanna, AppleWebKit, Blink (Chrome 28+ dropped the Blink token, so we
# infer Blink from Chrome when no other engine token is present).
_ENGINE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Gecko", _v(r"rv:(\d[\d.]*)")),
    ("Goanna", _v(r"Goanna/(\d[\d.]*)")),
    ("AppleWebKit", _v(r"AppleWebKit/(\d[\d.]*)")),
    ("KHTML", _v(r"KHTML/(\d[\d.]*)")),
    ("Trident", _v(r"Trident/(\d[\d.]*)")),
]


# --- OS patterns ----------------------------------------------------------
# Windows NT maps to a marketing version; we keep the NT version because it is
# unambiguous and the marketing name is not (e.g. NT 10.0 is both 10 and 11).
_OS_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Windows", _v(r"Windows NT (\d[\d.]*)")),
    ("Windows", _v(r"Windows (\d[\d.]*)")),
    ("macOS", _v(r"Mac OS X (\d[\d_]*)")),
    ("iOS", _v(r"iPhone OS (\d[\d_]*)")),
    ("iOS", _v(r"iPad.*OS (\d[\d_]*)")),
    ("iOS", _v(r"CPU OS (\d[\d_]*)")),
    ("Android", _v(r"Android (\d[\d.]*)")),
    ("Chrome OS", _v(r"CrOS ([\w\d]+)")),
    ("Linux", _v(r"Linux")),
]


# --- Device signals -------------------------------------------------------
# A small set of explicit tokens. We do not try to be clever about Android
# phone-vs-tablet because the UA rarely says which, and guessing produces
# support tickets.
_TABLET_RE = _v(r"iPad|Tablet|PlayBook|Silk")
_MOBILE_RE = _v(r"Mobi|iPhone|Android.*Mobile|Windows Phone|BlackBerry|Opera Mobi")


def _first_match(patterns: List[Tuple[str, re.Pattern]], ua: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (label, version) for the first matching pattern, else (None, None)."""
    for label, pat in patterns:
        m = pat.search(ua)
        if m:
            version = m.group(1) if m.groups() else None
            # Some patterns (e.g. bare "Linux") have no version group; guard.
            return label, version
    return None, None


def _normalize_version(version: Optional[str]) -> Optional[str]:
    """Strip trailing dots and underscores some UAs use in OS versions."""
    if version is None:
        return None
    # macOS / iOS versions sometimes use underscores: 10_15_7 -> 10.15.7
    v = version.replace("_", ".")
    # Trim trailing dots left by partial matches.
    v = v.rstrip(".")
    return v or None


def _infer_engine(browser: str, ua: str) -> Tuple[str, Optional[str]]:
    """Pick an engine when no explicit engine token matched.

    Chrome 28+ no longer ships a "Blink/" token, so a Chrome-family browser
    with an AppleWebKit token is actually running Blink. We report Blink with
    the AppleWebKit build number, since that is the closest stable identifier
    available.
    """
    if browser in ("Chrome", "Edge", "Opera", "Samsung Internet"):
        # These are all Chromium-based; engine is Blink. Use the Chrome build
        # version if present, else AppleWebKit build.
        m = re.search(r"Chrome/(\d[\d.]*)", ua, re.IGNORECASE)
        if m:
            return "Blink", m.group(1)
        return "Blink", None
    if browser == "Safari":
        m = re.search(r"AppleWebKit/(\d[\d.]*)", ua, re.IGNORECASE)
        if m:
            return "WebKit", m.group(1)
        return "WebKit", None
    if browser == "Firefox":
        m = re.search(r"Gecko/(\d[\d.]*)", ua, re.IGNORECASE)
        if m:
            return "Gecko", m.group(1)
        return "Gecko", None
    if browser == "IE":
        m = re.search(r"Trident/(\d[\d.]*)", ua, re.IGNORECASE)
        if m:
            return "Trident", m.group(1)
        return "Trident", None
    return "unknown", None


def _infer_device(os_name: str, ua: str) -> str:
    """Infer device class from OS and explicit mobile/tablet tokens."""
    if _TABLET_RE.search(ua):
        return "tablet"
    if os_name == "iOS":
        # iPad is caught above; iPhone is mobile.
        if "iPad" in ua:
            return "tablet"
        return "mobile"
    if os_name == "Android":
        # Android tablets usually omit "Mobile". This is the standard
        # heuristic; it is wrong sometimes, but it is the best available.
        if _MOBILE_RE.search(ua):
            return "mobile"
        return "tablet"
    if _MOBILE_RE.search(ua):
        return "mobile"
    if os_name in ("Windows", "macOS", "Linux", "Chrome OS"):
        return "desktop"
    return "unknown"


def parse_user_agent(ua: str) -> UserAgentResult:
    """Parse a User-Agent string.

    `ua` is the raw header value. If `ua` is empty or not a string, every
    field of the result is `"unknown"` (and versions `None`). We do not raise
    because User-Agent is untrusted input and logging code calls this.
    """
    if not isinstance(ua, str) or not ua:
        return UserAgentResult()

    browser, browser_version = _first_match(_BROWSER_PATTERNS, ua)
    browser_version = _normalize_version(browser_version)
    if browser is None:
        browser = "unknown"

    engine, engine_version = _infer_engine(browser, ua)
    if engine == "unknown":
        engine, engine_version = _first_match(_ENGINE_PATTERNS, ua)
    engine_version = _normalize_version(engine_version)
    if engine is None:
        engine = "unknown"

    os_name, os_version = _first_match(_OS_PATTERNS, ua)
    os_version = _normalize_version(os_version)
    if os_name is None:
        os_name = "unknown"

    device = _infer_device(os_name, ua)

    return UserAgentResult(
        browser=browser,
        browser_version=browser_version,
        engine=engine,
        engine_version=engine_version,
        os=os_name,
        os_version=os_version,
        device=device,
    )


# Public alias. Some callers prefer `parse`, others prefer the explicit name.
# Both point at the same function so there is one code path.
parse = parse_user_agent
