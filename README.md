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
```

Type an address and press Enter. You can leave the scheme off — `example.com`
becomes `https://example.com/`, while `localhost:8000` and `box.local` are
assumed to be plain http. Pick `POST`/`PUT`/`PATCH`/`DELETE` from the method
dropdown and a body editor appears with its own content-type field.

## Using it

| Tab | Shows |
|---|---|
| **Summary** | status, elapsed time, resolved IP, final URL, redirect count, server, cookies set — plus the full redirect chain |
| **Response headers** | every header exactly as returned |
| **Request** | the headers sent, and the request rebuilt as it went onto the wire |
| **Body** | pretty-printed JSON, aligned form fields, HTML as Reader or coloured Source, text decoded with the declared charset, or a hexdump for binary |
| **Links** | every link on an HTML page, text and href, in document order (HTML only) |
| **Raw** | the response as it came off the wire, status line and all |

### HTML pages

When the body is HTML, the Body tab gains a **Reader / Source** switch:

- **Reader** strips the markup and shows the prose — headings marked `#`, list
  items bulleted, image alt text inlined, and `script`/`style` content dropped.
- **Source** shows the markup itself, with tags, attributes, values and
  comments coloured.

The Summary tab also picks up the page title, meta description, language and
counts of links, images, scripts, stylesheets and forms.

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
| [fetcher.py](fetcher.py) | URL normalisation and the actual request |
| [exchange.py](exchange.py) | the `Exchange` value object |
| [formatting.py](formatting.py) | pure rendering helpers (body, raw, cURL, summary, filter) |
| [htmlreader.py](htmlreader.py) | HTML text extraction, page metadata, source colouring |
| [theme.py](theme.py) | palette, status colours, fonts, ttk styles |
| [url_bar.py](url_bar.py), [history.py](history.py), [detail.py](detail.py) | the three panes |
| [widgets.py](widgets.py) | shared Tk building blocks |

Each request runs on its own daemon thread and comes back to the GUI through a
`queue.Queue` that the Tk event loop drains every 60 ms no Tk calls happen off
the main thread, so the window never freezes mid-request.

Requests are sent with `Accept-Encoding: identity`, but CDNs compress anyway, so
gzip and deflate bodies are decompressed on arrival (and gzip is sniffed by magic
bytes when the header is missing). When that happens the Summary tab reports both
the decoded body size and what was actually transferred.

## Tests

```bash
python -m unittest discover -p "test_*.py"
```

58 tests: the formatting and HTML helpers run offline, and the fetcher tests
drive a throwaway `http.server` on localhost.
