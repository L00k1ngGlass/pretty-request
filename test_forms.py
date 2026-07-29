"""Tests for form parsing and the successful-control rules."""

from __future__ import annotations

import unittest
from urllib.parse import parse_qsl, urlsplit

from forms import URLENCODED, parse_forms, submit

PAGE_URL = "https://example.com/docs/index.html"

SEARCH_PAGE = """
<form id="search" action="/search">
  <input type="text" name="q" value="ada" required>
  <input type="hidden" name="scope" value="site">
  <input type="submit" name="go" value="Search">
</form>
"""

LOGIN_PAGE = """
<form name="login" method="POST" action="../session">
  <input type="email" name="email" value="ada@example.com">
  <input type="password" name="password">
  <input type="hidden" name="csrf" value="tok123">
  <input type="checkbox" name="remember" value="yes" checked>
  <input type="checkbox" name="newsletter">
  <input type="radio" name="plan" value="free">
  <input type="radio" name="plan" value="pro" checked>
  <select name="country"><option value="us">US</option><option value="uk" selected>UK</option></select>
  <select name="lang"><option value="en">English</option><option value="fr">French</option></select>
  <textarea name="bio">  hello  </textarea>
  <input type="text" name="ignored" disabled>
  <input type="text" value="nameless">
  <input type="reset" name="reset" value="Reset">
  <button type="submit" name="action" value="login">Log in</button>
</form>
"""


class ParseTest(unittest.TestCase):
    def test_action_and_method_defaults(self):
        form = parse_forms(SEARCH_PAGE, PAGE_URL)[0]
        self.assertEqual(form.method, "GET")  # method defaults to GET
        self.assertEqual(form.action, "https://example.com/search")
        self.assertEqual(form.enctype, URLENCODED)
        self.assertEqual(form.identifier, "form#search")

    def test_relative_action_resolves_against_the_page(self):
        form = parse_forms(LOGIN_PAGE, PAGE_URL)[0]
        self.assertEqual(form.action, "https://example.com/session")
        self.assertEqual(form.method, "POST")
        self.assertEqual(form.identifier, "form[name=login]")

    def test_empty_action_means_the_page_itself(self):
        form = parse_forms('<form><input name="a"></form>', PAGE_URL)[0]
        self.assertEqual(form.action, PAGE_URL)

    def test_base_tag_rebases_the_action(self):
        source = '<base href="https://cdn.example.com/app/"><form action="post"></form>'
        self.assertEqual(parse_forms(source, PAGE_URL)[0].action, "https://cdn.example.com/app/post")

    def test_fields_are_collapsed_for_the_editor(self):
        fields = {item.name: item for item in parse_forms(LOGIN_PAGE, PAGE_URL)[0].fields}
        self.assertEqual(fields["email"].kind, "text")
        self.assertEqual(fields["email"].input_type, "email")
        self.assertEqual(fields["csrf"].kind, "hidden")
        self.assertEqual(fields["csrf"].value, "tok123")
        self.assertEqual(fields["bio"].kind, "textarea")
        self.assertEqual(fields["bio"].value, "hello")
        self.assertTrue(fields["remember"].checked)
        self.assertFalse(fields["newsletter"].checked)
        self.assertTrue(fields["ignored"].disabled)

    def test_radios_become_one_choice_field(self):
        fields = {item.name: item for item in parse_forms(LOGIN_PAGE, PAGE_URL)[0].fields}
        self.assertEqual(fields["plan"].kind, "choice")
        self.assertEqual(fields["plan"].options, ("free", "pro"))
        self.assertEqual(fields["plan"].value, "pro")  # the checked one

    def test_fields_stay_in_document_order_including_radio_groups(self):
        names = [item.name for item in parse_forms(LOGIN_PAGE, PAGE_URL)[0].fields if item.name]
        self.assertEqual(
            names,
            ["email", "password", "csrf", "remember", "newsletter", "plan", "country", "lang",
             "bio", "ignored", "action"],
        )

    def test_select_defaults_to_selected_then_first_option(self):
        fields = {item.name: item for item in parse_forms(LOGIN_PAGE, PAGE_URL)[0].fields}
        self.assertEqual(fields["country"].value, "uk")  # marked selected
        self.assertEqual(fields["lang"].value, "en")  # nothing selected: first wins

    def test_reset_buttons_are_not_collected(self):
        names = [item.name for item in parse_forms(LOGIN_PAGE, PAGE_URL)[0].fields]
        self.assertNotIn("reset", names)

    def test_multiple_forms_and_broken_markup(self):
        self.assertEqual(len(parse_forms(SEARCH_PAGE + LOGIN_PAGE, PAGE_URL)), 2)
        self.assertEqual(len(parse_forms('<form action="/x"><input name="a">', PAGE_URL)), 1)
        self.assertEqual(parse_forms("", PAGE_URL), [])

    def test_controls_outside_a_form_are_ignored(self):
        self.assertEqual(parse_forms('<input name="loose">', PAGE_URL), [])


class SubmitTest(unittest.TestCase):
    def submit_login(self, **overrides):
        form = parse_forms(LOGIN_PAGE, PAGE_URL)[0]
        values = form.defaults()
        values.update(overrides)
        return form, submit(form, values, PAGE_URL)

    def test_get_form_builds_a_query_string(self):
        form = parse_forms(SEARCH_PAGE, PAGE_URL)[0]
        submission = submit(form, {"q": "grace hopper"}, PAGE_URL)
        self.assertEqual(submission.method, "GET")
        self.assertIsNone(submission.body)
        parts = urlsplit(submission.url)
        self.assertEqual(parts.path, "/search")
        self.assertEqual(
            parse_qsl(parts.query), [("q", "grace hopper"), ("scope", "site"), ("go", "Search")]
        )

    def test_get_form_replaces_an_existing_query(self):
        form = parse_forms('<form action="/s?old=1"><input name="q" value="new"></form>', PAGE_URL)[0]
        url = submit(form, {"q": "new"}, PAGE_URL).url
        self.assertEqual(url, "https://example.com/s?q=new")  # old=1 is gone, as in a browser

    def test_post_form_encodes_a_body(self):
        _, submission = self.submit_login()
        self.assertEqual(submission.method, "POST")
        self.assertEqual(submission.content_type, URLENCODED)
        self.assertEqual(submission.url, "https://example.com/session")
        fields = dict(parse_qsl(submission.body.decode()))
        self.assertEqual(fields["email"], "ada@example.com")
        self.assertEqual(fields["csrf"], "tok123")  # hidden tokens ride along

    def test_unchecked_boxes_are_absent_and_checked_ones_carry_their_value(self):
        _, submission = self.submit_login()
        fields = dict(parse_qsl(submission.body.decode()))
        self.assertEqual(fields["remember"], "yes")
        self.assertNotIn("newsletter", fields)

    def test_toggling_a_checkbox_off_removes_it(self):
        _, submission = self.submit_login(remember="")
        self.assertNotIn("remember", dict(parse_qsl(submission.body.decode())))

    def test_disabled_and_unnamed_controls_are_never_sent(self):
        _, submission = self.submit_login()
        body = submission.body.decode()
        self.assertNotIn("ignored", body)
        self.assertNotIn("nameless", body)

    def test_only_the_first_named_submit_contributes(self):
        _, submission = self.submit_login()
        fields = parse_qsl(submission.body.decode())
        self.assertIn(("action", "login"), fields)
        self.assertEqual(sum(1 for name, _ in fields if name == "action"), 1)

    def test_edited_values_win_over_defaults(self):
        _, submission = self.submit_login(email="grace@example.com", plan="free")
        fields = dict(parse_qsl(submission.body.decode()))
        self.assertEqual(fields["email"], "grace@example.com")
        self.assertEqual(fields["plan"], "free")

    def test_referer_is_the_page_the_form_came_from(self):
        _, submission = self.submit_login()
        self.assertEqual(submission.referer, PAGE_URL)

    def test_file_inputs_are_reported_as_skipped(self):
        form = parse_forms(
            '<form method="post" enctype="multipart/form-data" action="/up">'
            '<input type="file" name="avatar"><input name="title" value="x"></form>',
            PAGE_URL,
        )[0]
        submission = submit(form, form.defaults(), PAGE_URL)
        self.assertTrue(form.uploads_files)
        self.assertTrue(any("avatar" in note for note in submission.skipped))
        self.assertTrue(any("multipart" in note for note in submission.skipped))
        self.assertEqual(dict(parse_qsl(submission.body.decode())), {"title": "x"})


if __name__ == "__main__":
    unittest.main()
