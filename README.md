# User Agent Parser

Parses an HTTP `User-Agent` header into browser, engine, operating system, and device class. Standard library only, no dependencies.

```python
from user_agent_parser import parse, UserAgentResult

r: UserAgentResult = parse(
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
# r.browser == "Chrome", r.os == "Windows", r.device == "desktop"
```

`parse(ua: str) -> UserAgentResult` is the only function you need. `UserAgentResult` is a frozen dataclass with `browser`, `browser_version`, `engine`, `engine_version`, `os`, `os_version`, and `device` fields. Versions are strings or `None`; device is one of `"desktop"`, `"mobile"`, `"tablet"`, `"unknown"`.

## Why this exists

The use case is request logging and lightweight analytics where you want a stable, dependency-free classification of clients and cannot justify pulling in a maintained database of thousands of regexes. The trade-off is coverage: this library handles the common modern clients (Chrome, Firefox, Safari, Edge, Opera, Samsung Internet, IE, plus Windows / macOS / iOS / Android / Linux / Chrome OS) and returns `"unknown"` for everything else rather than guessing. If you need to distinguish Firefox 2.0 from Firefox 2.0.0.20, or identify a 2011-era BlackBerry build, use a heavier library.

## The awkward edge

Android phone-vs-tablet is not reliably encoded in the User-Agent. This library uses the standard heuristic: if the string contains `Mobile`, it is a phone; otherwise it is a tablet. That is wrong for some devices and there is no way to fix it from the UA alone. iPad is always reported as `tablet` because it says so explicitly. Windows on ARM is reported as `desktop`, which is correct for our purposes but not for yours if you care about CPU architecture.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```
