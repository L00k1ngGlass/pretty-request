"""Reading `<form>` elements off a page and submitting them like a browser would.

The fiddly part is not parsing, it is knowing which controls a browser actually
sends. The HTML spec calls them *successful controls*, and the rules bite:

  * a control with no `name` is never submitted;
  * a `disabled` control is never submitted;
  * an unchecked checkbox or radio is not submitted at all — checkboxes are
    absent rather than false, and a checked one with no `value` submits `on`;
  * a `select` submits its selected option, defaulting to the first;
  * only the submit button you actually clicked contributes its name/value;
  * `method` defaults to GET, and a GET form's fields *replace* whatever query
    string the action URL already had rather than appending to it;
  * an empty `action` means the page itself.

Hidden inputs are submitted as-is, which is why CSRF tokens and session nonces
live in them — they are shown in the editor so you can see what a submit carries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

URLENCODED = "application/x-www-form-urlencoded"
MULTIPART = "multipart/form-data"

# Widget classes the editor knows how to draw, keyed off the control.
TEXTUAL = (
    "text", "search", "email", "url", "tel", "password", "number", "range",
    "date", "time", "datetime-local", "month", "week", "color",
)


@dataclass(frozen=True)
class Field:
    """One editable control, already collapsed into something a GUI can draw."""

    name: str
    kind: str  # text | textarea | checkbox | choice | hidden | submit | file
    value: str = ""
    options: Tuple[str, ...] = ()
    checked: bool = False
    disabled: bool = False
    required: bool = False
    input_type: str = ""  # the original type, for the label

    @property
    def editable(self) -> bool:
        return self.kind in ("text", "textarea", "checkbox", "choice", "hidden")

    @property
    def label(self) -> str:
        kind = self.input_type or self.kind
        marks = "".join([" *" if self.required else "", " (disabled)" if self.disabled else ""])
        return "%s  ·  %s%s" % (self.name or "(unnamed)", kind, marks)


@dataclass(frozen=True)
class Form:
    """A form found on the page, with its action already resolved."""

    index: int
    identifier: str
    method: str
    action: str
    enctype: str
    fields: Tuple[Field, ...] = ()

    @property
    def label(self) -> str:
        return "%s — %s %s" % (self.identifier, self.method, self.action)

    @property
    def uploads_files(self) -> bool:
        return any(item.kind == "file" for item in self.fields)

    def defaults(self) -> Dict[str, str]:
        """Starting values, keyed by field name."""
        values: Dict[str, str] = {}
        for item in self.fields:
            if not item.name or item.kind == "submit":
                continue
            if item.kind == "checkbox":
                values[item.name] = item.value if item.checked else ""
            else:
                values[item.name] = item.value
        return values


@dataclass
class _Building:
    identifier: str
    method: str
    action: str
    enctype: str
    fields: List[Field] = field(default_factory=list)
    radios: Dict[str, List[Tuple[str, bool]]] = field(default_factory=dict)
    radio_slots: Dict[str, int] = field(default_factory=dict)  # keeps document order


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms: List[_Building] = []
        self._current: Optional[_Building] = None
        self._select: Optional[Dict] = None
        self._textarea: Optional[Dict] = None
        self._base = ""

    # -- structure ---------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag == "base" and attributes.get("href"):
            self._base = self._base or attributes["href"]
        elif tag == "form":
            self._start_form(attributes)
        elif tag == "input":
            self._add_input(attributes)
        elif tag == "select":
            self._select = {"attrs": attributes, "options": [], "selected": ""}
        elif tag == "option" and self._select is not None:
            self._select["pending"] = attributes
        elif tag == "textarea":
            self._textarea = {"attrs": attributes, "text": []}
        elif tag == "button" and attributes.get("type", "submit").lower() == "submit":
            self._add(attributes, kind="submit", input_type="submit")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self._finish_form()
        elif tag == "select":
            self._finish_select()
        elif tag == "textarea":
            self._finish_textarea()

    def handle_data(self, data):
        if self._textarea is not None:
            self._textarea["text"].append(data)
        elif self._select is not None and "pending" in self._select:
            pending = self._select.pop("pending")
            # An option's value defaults to its text content.
            value = pending.get("value", data.strip())
            self._select["options"].append(value)
            if "selected" in pending:
                self._select["selected"] = value

    # -- pieces ------------------------------------------------------------

    def _start_form(self, attributes):
        method = attributes.get("method", "get").upper()
        self._current = _Building(
            identifier=_identify(attributes, len(self.forms)),
            method=method if method in ("GET", "POST") else "GET",
            action=attributes.get("action", ""),
            enctype=attributes.get("enctype", URLENCODED).lower(),
        )

    def _finish_form(self):
        if self._current is None:
            return
        # Fill each radio group back into the slot its first button occupied, so
        # the submitted order matches the document as a browser's would.
        for name, choices in self._current.radios.items():
            checked = next((value for value, is_checked in choices if is_checked), "")
            self._current.fields[self._current.radio_slots[name]] = Field(
                name=name,
                kind="choice",
                value=checked or (choices[0][0] if choices else ""),
                options=tuple(value for value, _ in choices),
                input_type="radio",
            )
        self.forms.append(self._current)
        self._current = None

    def _add_input(self, attributes):
        input_type = attributes.get("type", "text").lower()
        if input_type == "radio":
            name = attributes.get("name", "")
            if name and self._current is not None:
                group = self._current.radios.setdefault(name, [])
                if not group:  # reserve this position for the whole group
                    self._current.radio_slots[name] = len(self._current.fields)
                    self._current.fields.append(Field(name=name, kind="choice", input_type="radio"))
                group.append((attributes.get("value", "on"), "checked" in attributes))
            return
        if input_type == "checkbox":
            self._add(attributes, kind="checkbox", input_type=input_type,
                      value=attributes.get("value", "on"), checked="checked" in attributes)
            return
        if input_type in ("submit", "image"):
            self._add(attributes, kind="submit", input_type=input_type)
            return
        if input_type in ("button", "reset"):
            return  # never submitted
        if input_type == "file":
            self._add(attributes, kind="file", input_type=input_type)
            return
        kind = "hidden" if input_type == "hidden" else "text"
        self._add(attributes, kind=kind, input_type=input_type)

    def _finish_select(self):
        if self._select is None:
            return
        state, self._select = self._select, None
        options = tuple(state["options"])
        # With nothing marked selected, a browser picks the first option.
        chosen = state["selected"] or (options[0] if options else "")
        self._add(state["attrs"], kind="choice", input_type="select", value=chosen, options=options)

    def _finish_textarea(self):
        if self._textarea is None:
            return
        state, self._textarea = self._textarea, None
        self._add(state["attrs"], kind="textarea", input_type="textarea",
                  value="".join(state["text"]).strip())

    def _add(self, attributes, *, kind, input_type, value=None, options=(), checked=False):
        if self._current is None:
            return  # a control outside any form; the HTML5 `form=` attribute is not handled
        self._current.fields.append(
            Field(
                name=attributes.get("name", ""),
                kind=kind,
                value=attributes.get("value", "") if value is None else value,
                options=tuple(options),
                checked=checked,
                disabled="disabled" in attributes,
                required="required" in attributes,
                input_type=input_type,
            )
        )


def _identify(attributes: Dict[str, str], index: int) -> str:
    for key, prefix in (("id", "form#"), ("name", "form[name=")):
        if attributes.get(key):
            suffix = "]" if key == "name" else ""
            return "%s%s%s" % (prefix, attributes[key], suffix)
    return "form %d" % (index + 1)


# -- public API ------------------------------------------------------------


def parse_forms(source: str, page_url: str = "") -> List[Form]:
    """Every form on the page, with actions resolved against ``page_url``."""
    parser = _FormParser()
    try:
        parser.feed(source)
        parser.close()
    except AssertionError:  # malformed markup; keep what we have
        pass
    if parser._current is not None:  # unclosed <form>
        parser._finish_form()

    base = urljoin(page_url, parser._base) if page_url else parser._base
    forms = []
    for index, built in enumerate(parser.forms):
        action = urljoin(base, built.action) if base else built.action
        forms.append(
            Form(
                index=index,
                identifier=built.identifier,
                method=built.method,
                action=action or page_url,
                enctype=built.enctype,
                fields=tuple(built.fields),
            )
        )
    return forms


@dataclass(frozen=True)
class Submission:
    """A request built from a filled-in form."""

    method: str
    url: str
    body: Optional[bytes]
    content_type: str
    referer: str
    skipped: Tuple[str, ...] = ()  # controls a browser would send but we cannot


def submit(form: Form, values: Dict[str, str], page_url: str = "") -> Submission:
    """Turn filled-in values into the request the browser would send."""
    pairs: List[Tuple[str, str]] = []
    skipped: List[str] = []
    used_submit = False

    for item in form.fields:
        if not item.name or item.disabled:
            continue
        if item.kind == "file":
            skipped.append("%s (file upload needs multipart)" % item.name)
            continue
        if item.kind == "submit":
            # Only the button you click is submitted, so take the first named one.
            if not used_submit and item.value:
                pairs.append((item.name, item.value))
                used_submit = True
            continue
        value = values.get(item.name, item.value)
        if item.kind == "checkbox" and not value:
            continue  # unchecked boxes are absent, not false
        pairs.append((item.name, value))

    encoded = urlencode(pairs)
    if form.method == "GET":
        parts = urlsplit(form.action)
        # A GET form replaces the action's query string rather than extending it.
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, encoded, ""))
        return Submission("GET", url, None, "", page_url, tuple(skipped))

    if form.enctype.startswith(MULTIPART):
        skipped.append("multipart encoding not supported; sent as %s" % URLENCODED)
    return Submission(
        "POST", form.action, encoded.encode(), URLENCODED, page_url, tuple(skipped)
    )
