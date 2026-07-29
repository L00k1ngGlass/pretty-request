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
| **Body** | pretty-printed JSON, aligned form fields, text decoded with the declared charset, or a hexdump for binary |
| **Raw** | the response as it came off the wire, status line and all |

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
| [theme.py](theme.py) | palette, status colours, fonts, ttk styles |
| [url_bar.py](url_bar.py), [history.py](history.py), [detail.py](detail.py) | the three panes |
| [widgets.py](widgets.py) | shared Tk building blocks |

Each request runs on its own daemon thread and comes back to the GUI through a
`queue.Queue` that the Tk event loop drains every 60 ms no Tk calls happen off
the main thread, so the window never freezes mid-request.

Requests are sent with `Accept-Encoding: identity` so bodies arrive readable;
urllib would not decompress gzip for us.

## Tests

```bash
python -m unittest discover -p "test_*.py"
```

33 tests: the formatting helpers run offline, and the fetcher tests drive a
throwaway `http.server` on localhost.
