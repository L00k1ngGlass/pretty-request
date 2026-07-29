"""Tests for the header profiles — order and semantics both matter."""

from __future__ import annotations

import unittest

import profiles
from profiles import ACCEPT_ENCODING, DEFAULT_PROFILE, PROFILES, headers_for, names

URL = "https://example.com/search?q=ada"


def header_names(headers):
    return [name for name, _ in headers]


def as_dict(headers):
    return {name.lower(): value for name, value in headers}


class RegistryTest(unittest.TestCase):
    def test_default_profile_exists_and_is_listed_first(self):
        self.assertIn(DEFAULT_PROFILE, PROFILES)
        self.assertEqual(names()[0], DEFAULT_PROFILE)

    def test_every_profile_identifies_itself_and_states_encodings(self):
        for name, profile in PROFILES.items():
            with self.subTest(profile=name):
                headers = as_dict(profile.navigation)
                self.assertIn("user-agent", headers)
                self.assertIn("accept", headers)
                # Never advertise br/zstd: the stdlib cannot decompress them.
                self.assertEqual(headers["accept-encoding"], ACCEPT_ENCODING)
                self.assertNotIn("br", headers["accept-encoding"])
                self.assertNotIn("zstd", headers["accept-encoding"])

    def test_unknown_profile_falls_back_to_the_default(self):
        self.assertEqual(headers_for("Netscape 4", url=URL), headers_for(DEFAULT_PROFILE, url=URL))


class NavigationTest(unittest.TestCase):
    def setUp(self):
        self.headers = headers_for("Chrome (macOS)", url=URL)
        self.lookup = as_dict(self.headers)

    def test_host_comes_first(self):
        self.assertEqual(self.headers[0], ("Host", "example.com"))

    def test_order_follows_the_real_browser(self):
        order = header_names(self.headers)
        self.assertLess(order.index("sec-ch-ua"), order.index("User-Agent"))
        self.assertLess(order.index("User-Agent"), order.index("Accept"))
        self.assertLess(order.index("Accept"), order.index("Sec-Fetch-Site"))
        self.assertEqual(order[-1], "Priority")

    def test_navigation_semantics(self):
        self.assertEqual(self.lookup["sec-fetch-mode"], "navigate")
        self.assertEqual(self.lookup["sec-fetch-dest"], "document")
        self.assertEqual(self.lookup["sec-fetch-site"], "none")  # typed in the address bar
        self.assertEqual(self.lookup["sec-fetch-user"], "?1")
        self.assertEqual(self.lookup["upgrade-insecure-requests"], "1")
        self.assertNotIn("origin", self.lookup)
        self.assertNotIn("content-length", self.lookup)

    def test_client_hints_agree_with_the_user_agent_version(self):
        self.assertIn("Chrome/%s" % profiles.CHROME_VERSION, self.lookup["user-agent"])
        self.assertIn('v="%s"' % profiles.CHROME_VERSION, self.lookup["sec-ch-ua"])
        self.assertEqual(self.lookup["sec-ch-ua-mobile"], "?0")
        self.assertEqual(self.lookup["sec-ch-ua-platform"], '"macOS"')

    def test_firefox_sends_no_client_hints(self):
        lookup = as_dict(headers_for("Firefox (macOS)", url=URL))
        self.assertNotIn("sec-ch-ua", lookup)
        self.assertIn("Firefox/", lookup["user-agent"])
        self.assertEqual(lookup["accept-language"], "en-US,en;q=0.5")

    def test_iphone_profile_is_mobile(self):
        lookup = as_dict(headers_for("iPhone Safari", url=URL))
        self.assertIn("iPhone", lookup["user-agent"])
        self.assertIn("Mobile/", lookup["user-agent"])

    def test_curl_profile_stays_minimal(self):
        headers = headers_for("curl", url=URL)
        self.assertEqual(header_names(headers), ["Host", "User-Agent", "Accept", "Accept-Encoding"])


class ScriptedRequestTest(unittest.TestCase):
    """A request with a body is what fetch()/XHR would send, not a navigation."""

    def setUp(self):
        self.headers = headers_for(
            "Chrome (macOS)", url=URL, method="POST", body=b'{"a":1}', content_type="application/json"
        )
        self.lookup = as_dict(self.headers)

    def test_sec_fetch_switches_to_cors(self):
        self.assertEqual(self.lookup["sec-fetch-mode"], "cors")
        self.assertEqual(self.lookup["sec-fetch-dest"], "empty")
        self.assertEqual(self.lookup["sec-fetch-site"], "same-origin")

    def test_navigation_only_headers_are_dropped(self):
        self.assertNotIn("sec-fetch-user", self.lookup)
        self.assertNotIn("upgrade-insecure-requests", self.lookup)

    def test_origin_is_added_before_the_sec_fetch_block(self):
        order = header_names(self.headers)
        self.assertEqual(order[order.index("Origin") + 1], "Sec-Fetch-Site")
        self.assertEqual(self.lookup["origin"], "https://example.com")

    def test_accept_and_priority_match_a_script_request(self):
        self.assertEqual(self.lookup["accept"], "*/*")
        self.assertEqual(self.lookup["priority"], "u=1, i")

    def test_content_headers_come_last(self):
        self.assertEqual(header_names(self.headers)[-2:], ["Content-Type", "Content-Length"])
        self.assertEqual(self.lookup["content-length"], "7")

    def test_body_less_post_still_counts_as_scripted(self):
        lookup = as_dict(headers_for("Chrome (macOS)", url=URL, method="DELETE"))
        self.assertEqual(lookup["sec-fetch-mode"], "cors")
        self.assertNotIn("content-length", lookup)

    def test_referer_is_included_when_given(self):
        headers = headers_for("Chrome (macOS)", url=URL, referer="https://example.com/")
        self.assertEqual(as_dict(headers)["referer"], "https://example.com/")


if __name__ == "__main__":
    unittest.main()
