# Loopy desktop app

A thin Electron shell around the Loopy backend. The whole UI lives in the
Python package ([ninexf/webapp.py](../ninexf/webapp.py)) and works in any
browser — this wrapper adds a native dark window and a native folder picker.
Release builds include a standalone `loopy-backend` executable, so users do
not need Python or `pip install -e .` just to launch Loopy.

## Run it

Development requires Node.js and Python 3:

```bash
# once, from the repo root
pip install -e .

# then
cd app
npm install
npm start
```

In development, the app spawns `python3 -m ninexf app --no-browser` with its
local copy of `ninexf` on `PYTHONPATH`, then opens the window. Release builds
spawn the bundled `backend-bin/loopy-backend` executable instead. If you
already have `ninexf app` running from the CLI, the desktop app reuses it.

Environment overrides: `NINEXF_PYTHON` (python executable), `NINEXF_PORT`
(default 9118).

## macOS release builds

The first publishable path is macOS-first:

```bash
cd app
npm install
npm run make:mac
```

That emits release artifacts under [app/out/make](/Users/manaskandimalla/Desktop/2026-Projects/Loops-Experimentation/app/out/make), including:

- [Loopy-0.6.0-arm64.dmg](/Users/manaskandimalla/Desktop/2026-Projects/Loops-Experimentation/app/out/make/Loopy-0.6.0-arm64.dmg)
- [Loopy-darwin-arm64-0.6.0.zip](/Users/manaskandimalla/Desktop/2026-Projects/Loops-Experimentation/app/out/make/zip/darwin/arm64/Loopy-darwin-arm64-0.6.0.zip)

## GitHub Releases publish flow

Electron Forge is now configured to publish Loopy to GitHub Releases as a draft:

```bash
cd app
export GITHUB_TOKEN=...
npm run publish:mac
```

That uses [app/forge.config.js](/Users/manaskandimalla/Desktop/2026-Projects/Loops-Experimentation/app/forge.config.js) and uploads the generated macOS artifacts to the repository's Releases tab.

## No Node? No problem

The identical UI without Electron:

```bash
python3 -m ninexf app
```

opens the same chat interface in your default browser.
