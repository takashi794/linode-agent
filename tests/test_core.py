# Tests for user_agent_parser.core

import unittest

from user_agent_parser import parse, parse_user_agent, UserAgentResult


class TestParseUserAgent(unittest.TestCase):
    def test_chrome_on_windows(self):
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "Chrome")
        self.assertEqual(r.browser_version, "120.0.0.0")
        self.assertEqual(r.os, "Windows")
        self.assertEqual(r.os_version, "10.0")
        self.assertEqual(r.engine, "Blink")
        self.assertEqual(r.device, "desktop")

    def test_edge_spoofing_chrome(self):
        # Edge contains "Chrome" and "Safari"; Edg/ must win.
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "Edge")
        self.assertEqual(r.browser_version, "120.0.0.0")
        self.assertEqual(r.engine, "Blink")

    def test_firefox_on_linux(self):
        ua = (
            "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) "
            "Gecko/20100101 Firefox/121.0"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "Firefox")
        self.assertEqual(r.browser_version, "121.0")
        self.assertEqual(r.os, "Linux")
        self.assertIsNone(r.os_version)
        self.assertEqual(r.engine, "Gecko")
        self.assertEqual(r.device, "desktop")

    def test_safari_on_macos(self):
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.1 Safari/605.1.15"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "Safari")
        self.assertEqual(r.browser_version, "17.1")
        self.assertEqual(r.os, "macOS")
        self.assertEqual(r.os_version, "10.15.7")
        self.assertEqual(r.engine, "WebKit")
        self.assertEqual(r.device, "desktop")

    def test_ipad(self):
        ua = (
            "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.1 Mobile/15E148 Safari/604.1"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "Safari")
        self.assertEqual(r.os, "iOS")
        self.assertEqual(r.os_version, "17.1")
        self.assertEqual(r.device, "tablet")

    def test_iphone(self):
        ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.4 Mobile/15E148 Safari/604.1"
        )
        r = parse(ua)
        self.assertEqual(r.os, "iOS")
        self.assertEqual(r.device, "mobile")

    def test_android_phone(self):
        ua = (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Mobile Safari/537.36"
        )
        r = parse(ua)
        self.assertEqual(r.os, "Android")
        self.assertEqual(r.os_version, "13")
        self.assertEqual(r.browser, "Chrome")
        self.assertEqual(r.device, "mobile")

    def test_android_tablet_no_mobile_token(self):
        # No "Mobile" token -> we infer tablet. This is the documented
        # heuristic and the test pins it.
        ua = (
            "Mozilla/5.0 (Linux; Android 12; SM-X906) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        )
        r = parse(ua)
        self.assertEqual(r.device, "tablet")

    def test_opera_chromium(self):
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "Opera")
        self.assertEqual(r.browser_version, "106.0.0.0")
        self.assertEqual(r.engine, "Blink")

    def test_ie11_trident(self):
        # IE11 in some configurations has no MSIE token.
        ua = (
            "Mozilla/5.0 (Windows NT 6.3; Trident/7.0; rv:11.0) "
            "like Gecko"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "IE")
        self.assertEqual(r.browser_version, "11.0")
        self.assertEqual(r.os, "Windows")
        self.assertEqual(r.os_version, "6.3")
        self.assertEqual(r.engine, "Trident")

    def test_samsung_internet(self):
        ua = (
            "Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-S918B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "SamsungBrowser/22.0 Chrome/111.0.5563.116 Mobile Safari/537.36"
        )
        r = parse(ua)
        self.assertEqual(r.browser, "Samsung Internet")
        self.assertEqual(r.browser_version, "22.0")
        self.assertEqual(r.device, "mobile")

    def test_empty_string(self):
        r = parse("")
        self.assertEqual(r.browser, "unknown")
        self.assertIsNone(r.browser_version)
        self.assertEqual(r.os, "unknown")
        self.assertEqual(r.device, "unknown")

    def test_non_string_input(self):
        # We do not raise on bad input; User-Agent is untrusted.
        r = parse(None)  # type: ignore[arg-type]
        self.assertEqual(r.browser, "unknown")
        self.assertEqual(r.device, "unknown")

    def test_completely_unknown_ua(self):
        r = parse("curl/8.4.0")
        self.assertEqual(r.browser, "unknown")
        self.assertEqual(r.os, "unknown")
        self.assertEqual(r.device, "unknown")

    def test_parse_alias_is_same_function(self):
        self.assertIs(parse, parse_user_agent)

    def test_result_is_frozen(self):
        r = parse("Mozilla/5.0 (Windows NT 10.0) Chrome/120.0.0.0")
        with self.assertRaises(Exception):
            r.browser = "Firefox"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
