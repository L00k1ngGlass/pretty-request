"""Tests for the HTML extractor — messy markup included."""

from __future__ import annotations

import unittest

from htmlreader import highlight, link_rows, looks_like_html, page_rows, to_text

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Ada &amp; Co</title>
  <meta name="description" content="Engineering, mostly">
  <meta property="og:title" content="ignored, title wins">
  <link rel="stylesheet" href="/site.css">
  <style>body { color: red }</style>
  <script>console.log("not prose");</script>
</head>
<body>
  <h1>Welcome</h1>
  <p>Hello <b>world</b> &mdash; nice to meet you.</p>
  <h2>Details</h2>
  <ul><li>first</li><li>second</li></ul>
  <a href="/about">About</a> and <a href="https://example.com">Example</a>
  <img src="cat.png" alt="a cat">
  <!-- a comment -->
  <form><input name="q"></form>
</body>
</html>"""


class DetectionTest(unittest.TestCase):
    def test_content_type_wins(self):
        self.assertTrue(looks_like_html("text/html", ""))
        self.assertFalse(looks_like_html("application/json", "<html>"))

    def test_sniffs_when_type_is_missing(self):
        self.assertTrue(looks_like_html("", "<!DOCTYPE html><html>"))
        self.assertTrue(looks_like_html("", "\n  <html lang='en'>"))
        self.assertFalse(looks_like_html("", "plain words"))


class ToTextTest(unittest.TestCase):
    def setUp(self):
        self.text = to_text(PAGE)

    def test_drops_markup_scripts_and_styles(self):
        self.assertNotIn("<", self.text)
        self.assertNotIn("console.log", self.text)
        self.assertNotIn("color: red", self.text)
        self.assertNotIn("a comment", self.text)

    def test_keeps_prose_and_decodes_entities(self):
        self.assertIn("Hello world — nice to meet you.", self.text)

    def test_marks_headings_and_list_items(self):
        self.assertIn("# Welcome", self.text)
        self.assertIn("## Details", self.text)
        self.assertIn("• first", self.text)
        self.assertIn("• second", self.text)

    def test_images_become_alt_text(self):
        self.assertIn("[image: a cat]", self.text)

    def test_no_runs_of_blank_lines(self):
        self.assertNotIn("\n\n\n", self.text)

    def test_survives_broken_markup(self):
        self.assertIn("dangling", to_text("<p>dangling <b>bold <div>x</p"))
        self.assertEqual(to_text(""), "")


class PageRowsTest(unittest.TestCase):
    def setUp(self):
        self.rows = dict(page_rows(PAGE))

    def test_metadata(self):
        self.assertEqual(self.rows["Page title"], "Ada & Co")
        self.assertEqual(self.rows["Description"], "Engineering, mostly")
        self.assertEqual(self.rows["Language"], "en")
        self.assertEqual(self.rows["Meta charset"], "utf-8")

    def test_counts(self):
        self.assertEqual(self.rows["Links"], "2")
        self.assertEqual(self.rows["Images"], "1")
        self.assertEqual(self.rows["Scripts"], "1")
        self.assertEqual(self.rows["Stylesheets / links"], "1")
        self.assertEqual(self.rows["Forms / inputs"], "1 / 1")

    def test_headings_listed_in_order(self):
        self.assertEqual(self.rows["Headings"], "Welcome, Details")


class LinkRowsTest(unittest.TestCase):
    def test_text_and_href_in_document_order(self):
        self.assertEqual(
            link_rows(PAGE), [("About", "/about"), ("Example", "https://example.com")]
        )

    def test_relative_hrefs_resolve_against_the_page(self):
        rows = dict((text, href) for text, href in link_rows(PAGE, "https://python.org/downloads/"))
        self.assertEqual(rows["About"], "https://python.org/about")
        self.assertEqual(rows["Example"], "https://example.com")  # absolute is left alone

    def test_relative_href_without_leading_slash_is_page_relative(self):
        rows = link_rows('<a href="next">n</a>', "https://example.com/docs/intro")
        self.assertEqual(rows[0][1], "https://example.com/docs/next")

    def test_base_tag_wins_over_the_page_url(self):
        source = '<base href="https://cdn.example.com/v2/"><a href="app.js">js</a>'
        self.assertEqual(link_rows(source, "https://example.com/")[0][1], "https://cdn.example.com/v2/app.js")

    def test_non_http_schemes_survive_resolution(self):
        source = '<a href="mailto:ada@example.com">mail</a><a href="#top">top</a>'
        hrefs = [href for _, href in link_rows(source, "https://example.com/page")]
        self.assertEqual(hrefs[0], "mailto:ada@example.com")
        self.assertEqual(hrefs[1], "https://example.com/page#top")

    def test_empty_link_text_is_labelled(self):
        self.assertEqual(link_rows('<a href="/x"></a>'), [("(no text)", "/x")])

    def test_limit_is_respected(self):
        many = "".join('<a href="/%d">%d</a>' % (i, i) for i in range(10))
        self.assertEqual(len(link_rows(many, limit=3)), 3)


class HighlightTest(unittest.TestCase):
    def test_spans_land_on_the_right_substrings(self):
        source = '<!doctype html><p class="lead">hi</p><!-- note -->'
        spans = highlight(source)
        found = {(kind, source[start:end]) for kind, start, end in spans}
        self.assertIn(("doctype", "<!doctype html>"), found)
        self.assertIn(("tag", "p"), found)
        self.assertIn(("attr", "class"), found)
        self.assertIn(("value", '"lead"'), found)
        self.assertIn(("comment", "<!-- note -->"), found)

    def test_plain_text_produces_no_spans(self):
        self.assertEqual(highlight("no markup here"), [])

    def test_limit_caps_the_work(self):
        source = "<b>x</b>" * 1000  # 2000 tags, two spans each
        self.assertEqual(len(highlight(source)), 4000)
        self.assertEqual(len(highlight(source, limit=80)), 40)  # only the first 10 copies


if __name__ == "__main__":
    unittest.main()
