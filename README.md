# pretty-request

A lightweight tkinter inspector for HTTP requests. Type a website address, hit
Send, and the whole exchange is laid out for you: status, timing, resolved IP,
redirect chain, request and response headers.



## Setup

Requires Python 3.9+

```bash
brew install python-tk@3.14      # only if `python3 -c "import tkinter"` fails

python3 -m venv .venv
source .venv/bin/activate
```

## Run

```bash
python app.py                                   # start empty
python app.py example.com                       # load an address immediately
python app.py https://api.github.com/zen -t 5   # 5 second timeout
python app.py example.com -p "Firefox (macOS)"  # send as a different client
```

Type an address and press Enter. You can leave the scheme off — `example.com`
becomes `https://example.com/`, while `localhost:8000` and `box.local` are
assumed to be plain http. Pick `POST`/`PUT`/`PATCH`/`DELETE` from the method
dropdown and a body editor appears with its own content-type field.

## Header profiles

The **send as** picker (bottom right) chooses which client you present as, because
servers vary the response on far more than the User-Agent:

| Profile | Headers | What it demonstrates |
|---|---|---|
| **Chrome (macOS)** — default | 15 | Client Hints (`sec-ch-ua`, `-mobile`, `-platform`), the full `Accept` q-value list, `Sec-Fetch-*`, `Priority` |
| **Firefox (macOS)** | 12 | No Client Hints at all, and `Accept-Language: …;q=0.5` rather than `0.9` |
| **Safari (macOS)** | 10 | WebKit's order: `Accept` first, `User-Agent` midway down |
| **iPhone Safari** | 10 | The UA that triggers mobile layouts |
| **curl** | 5 | What curl really sends: three headers |
| **pretty-request** | 5 | Honest identification |

Order is part of the fingerprint, so each profile is an ordered list copied from
the real thing. The `Sec-Fetch-*` family also changes meaning by request type,
and [profiles.py](profiles.py) models that: a typed-in address is a navigation
(`Sec-Fetch-Mode: navigate`, `Dest: document`, `Site: none`, `User: ?1`,
`Upgrade-Insecure-Requests: 1`), while anything carrying a body is what a page's
`fetch()` would send (`Mode: cors`, `Dest: empty`, `Site: same-origin`, an
`Origin` header, `Accept: */*`, `Priority: u=1, i`, and no navigation-only
headers).

Three deliberate deviations, all visible in the Request tab, which shows what
went on the wire rather than what we asked for:

- **`Accept-Encoding` is `gzip, deflate`.** Browsers add `br` and `zstd`; the
  standard library cannot decompress either. Ask for what you can read.
- **Field names are title-cased** — `sec-ch-ua` leaves as `Sec-Ch-Ua`. urllib
  does this in `do_open`. Legal, since field names are case-insensitive.
- **`Connection: close`** is forced by urllib, which does not pool connections.

This makes you look like a browser to anything reading headers. It will not
defeat real bot detection, which fingerprints the TLS handshake (JA3/JA4) and
HTTP/2 frame ordering — urllib speaks HTTP/1.1 with Python's TLS stack, and no
header set changes that. Use it to see the page a browser would get, and respect
the robots.txt and terms of the sites you point it at.

## Using it

| Tab | Shows |
|---|---|
| **Summary** | status, elapsed time, resolved IP, profile sent as, final URL, redirect count, server, cookies set — plus the full redirect chain |
| **Response headers** | every header exactly as returned |
| **Request** | the headers sent, and the request rebuilt as it went onto the wire |
| **Body** | pretty-printed JSON, aligned form fields, HTML as Reader or coloured Source, text decoded with the declared charset, or a hexdump for binary |
| **Links** | every link on an HTML page, text and href, in document order, with **Copy link** / **Copy all** (HTML only) |
| **Forms** | the page's forms, as fillable inputs you can submit (HTML only) |
| **Raw** | the response as it came off the wire, status line and all |

### HTML pages

When the body is HTML, the Body tab gains a **Reader / Source** switch:

- **Reader** strips the markup and shows the prose — headings marked `#`, list
  items bulleted, image alt text inlined, and `script`/`style` content dropped.
- **Source** shows the markup itself, with tags, attributes, values and
  comments coloured.

The Summary tab also picks up the page title, meta description, language and
counts of links, images, scripts, stylesheets and forms.

The **Links** tab lists every link on the page. Hrefs are resolved to absolute
URLs against the final URL after redirects — or against the page's own
`<base href>` when it has one — so what you copy works on its own. Double-click
a row (or **Copy link**) to copy one; **Copy all** copies every href, one per
line, ready to pipe into something else.

### Filling in forms

The **Forms** tab reads the `<form>` tags off the page you just fetched and
draws each control as a real widget — text boxes, checkboxes, dropdowns for
`select` and radio groups, textareas — pre-filled with the page's own defaults.
Edit what you like and hit **Submit form**; the app builds the request the
browser would have built and sends it, so the result lands in the history like
any other. **Copy as cURL** gives you the same request as a command.

[forms.py](forms.py) implements the HTML rules for *successful controls*, which
is where hand-rolled form posts usually go wrong:

- a control with no `name`, or a `disabled` one, is never submitted;
- an unchecked checkbox is **absent** rather than false, and a checked one with
  no `value` submits `on`;
- a `select` submits its selected option, defaulting to the first;
- only the submit button you actually clicked contributes its name and value;
- `method` defaults to GET, and a GET form's fields **replace** the action URL's
  existing query string instead of appending to it;
- an empty `action` means the page itself, and a relative one resolves against
  the page (or its `<base href>`);
- fields submit in document order, radio groups included;
- hidden inputs ride along untouched — which is how CSRF tokens survive, and why
  they are shown in the editor rather than hidden from you.

A submitted form is a **document navigation even when it POSTs**, so it goes out
with `Sec-Fetch-Mode: navigate`, `Sec-Fetch-Dest: document`, the page as
`Referer`, and an `Origin` — not the `cors`/`empty` pair a script's `fetch()`
would send. `Sec-Fetch-Site` is derived from the referer: `same-origin` or
`cross-site`.

File inputs are the one gap: they need `multipart/form-data`, so they are
skipped and named in the status line rather than silently dropped.

This is an extractor, not a rendering engine: no layout, no CSS, no JavaScript.
Actually painting a page in Tk would mean a dependency like `tkinterweb`, which
bundles a Tkhtml binary.

Rows in the history list are coloured by status class (2xx green, 3xx purple,
4xx amber, 5xx red, failures red). The filter box matches on status, method,
URL and response headers. **Copy as cURL** puts a replayable command on the
clipboard. `⌘L` focuses the address bar, `⌘K` clears the history.

Requests that never get a response bad DNS, refused connection, timeout, TLS
failure are listed too, with the reason on the Summary tab rather than a
dialog box.

## Layout

| File | Role |
|---|---|
| [app.py](app.py) | window, worker threads, queue draining |
| [fetcher.py](fetcher.py) | URL normalisation, the actual request, decompression |
| [profiles.py](profiles.py) | browser header profiles and Sec-Fetch semantics |
| [exchange.py](exchange.py) | the `Exchange` value object |
| [formatting.py](formatting.py) | pure rendering helpers (body, raw, cURL, summary, filter) |
| [htmlreader.py](htmlreader.py) | HTML text extraction, page metadata, source colouring |
| [forms.py](forms.py) | form parsing and the successful-control submission rules |
| [theme.py](theme.py) | palette, status colours, fonts, ttk styles |
| [url_bar.py](url_bar.py), [history.py](history.py), [detail.py](detail.py) | the three panes |
| [widgets.py](widgets.py) | shared Tk building blocks |

Each request runs on its own daemon thread and comes back to the GUI through a
`queue.Queue` that the Tk event loop drains every 60 ms no Tk calls happen off
the main thread, so the window never freezes mid-request.

Every profile advertises `Accept-Encoding: gzip, deflate`, so bodies are
decompressed on arrival — and gzip is sniffed by magic bytes when a CDN omits the
header, which happens. The Summary tab then reports both the decoded body size
and what was actually transferred.

## Tests

```bash
python -m unittest discover -p "test_*.py"
```

108 tests: the formatting, HTML, form and profile helpers run offline, and the
fetcher tests drive a throwaway `http.server` on localhost.
