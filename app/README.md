# 9xf desktop app

A thin Electron shell around the `9xf app` server. The whole UI lives in the
Python package ([ninexf/webapp.py](../ninexf/webapp.py)) and works in any
browser — this wrapper adds a native dark window and a native folder picker.

## Run it

Requires Node.js and a Python with `ninexf` importable:

```bash
# once, from the repo root
pip install -e .

# then
cd app
npm install
npm start
```

The app spawns `python3 -m ninexf app --no-browser`, waits for it, and opens
the window. If you already have `9xf app` running (from the CLI), it reuses it.

Environment overrides: `NINEXF_PYTHON` (python executable), `NINEXF_PORT`
(default 9118).

## No Node? No problem

The identical UI without Electron:

```bash
9xf app
```

opens the same chat interface in your default browser.
