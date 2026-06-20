// Loopy desktop app: a thin Electron shell around the `ninexf app` server.
// It starts the bundled Loopy backend executable, waits for it to come up, and
// hosts it in a native window with a native folder picker bridged via preload.js.

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const net = require('net');
const path = require('path');
// const updateElectronApp = require('update-electron-app');

const DEFAULT_PORT = Number(process.env.NINEXF_PORT || 9118);
const PYTHON = process.env.NINEXF_PYTHON || 'python3';
const REQUIRED_MODEL = 'openrouter/openrouter/free';
let port = DEFAULT_PORT;
let url = `http://127.0.0.1:${port}`;

let server = null;
let win = null;
let spawnedHere = false;

// Temporarily disabled - needs ESM import fix
// updateElectronApp({
//   updateInterval: '1 hour',
//   logger: console,
//   notifyUser: true,
// });

function backendRoot() {
  return path.join(app.getAppPath(), 'backend');
}

function backendExecutablePath() {
  return path.join(app.getAppPath(), 'backend-bin', 'loopy-backend');
}

function backendModulePath() {
  return path.join(backendRoot(), 'ninexf', '__main__.py');
}

function ping(cb) {
  http.get(`${url}/api/runs`, res => cb(res.statusCode === 200))
    .on('error', () => cb(false));
}

function hasCurrentModelList(cb) {
  http.get(`${url}/api/models`, res => {
    let body = '';
    res.setEncoding('utf8');
    res.on('data', chunk => { body += chunk; });
    res.on('end', () => {
      try {
        const data = JSON.parse(body);
        const models = Array.isArray(data.models) ? data.models : [];
        cb(models.includes(REQUIRED_MODEL));
      } catch {
        cb(false);
      }
    });
  }).on('error', () => cb(false));
}

function findOpenPort(start, cb) {
  const candidate = Number(start);
  const probe = net.createServer();
  probe.once('error', () => findOpenPort(candidate + 1, cb));
  probe.once('listening', () => {
    probe.close(() => cb(candidate));
  });
  probe.listen(candidate, '127.0.0.1');
}

function startServer(onStarted) {
  const bundledBackend = backendRoot();
  const backendExecutable = backendExecutablePath();
  const modulePath = backendModulePath();
  const hasExecutable = fs.existsSync(backendExecutable);
  const hasSourceFallback = fs.existsSync(modulePath);
  if (!hasExecutable && !hasSourceFallback) {
    dialog.showErrorBox(
      'Loopy backend is missing',
      `Loopy could not find its bundled backend at:\n${backendExecutable}\n\nRebuild the app bundle before distributing it.`,
    );
    app.quit();
    return;
  }
  const command = hasExecutable ? backendExecutable : PYTHON;
  const args = hasExecutable
    ? ['app', '--port', String(port), '--no-browser']
    : ['-m', 'ninexf', 'app', '--port', String(port), '--no-browser'];
  const pythonPath = [bundledBackend, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  server = spawn(command, args, {
    cwd: hasExecutable ? path.dirname(backendExecutable) : bundledBackend,
    stdio: ['ignore', 'inherit', 'inherit'],
    env: {
      ...process.env,
      ...(hasExecutable ? {} : { PYTHONPATH: pythonPath }),
    },
  });
  spawnedHere = true;
  server.on('error', err => {
    if (win && !win.isDestroyed()) {
      dialog.showErrorBox(
        'Loopy could not launch its backend',
        `${String(err.message || err)}\n\nBackend path: ${command}`,
      );
    }
  });
  server.on('exit', code => {
    if (win && !win.isDestroyed() && code !== 0 && code !== null) {
      dialog.showErrorBox('Loopy backend stopped',
        `The backend exited (code ${code}).\n` +
        `Backend path: ${command}`);
    }
  });
  if (onStarted) onStarted();
}

function waitForServer(retries, cb) {
  ping(ok => {
    if (ok) return cb(true);
    if (retries <= 0) return cb(false);
    setTimeout(() => waitForServer(retries - 1, cb), 250);
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 980,
    minHeight: 600,
    backgroundColor: '#161513',
    title: 'Loopy',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.webContents.setWindowOpenHandler(({ url: target }) => {
    shell.openExternal(target);
    return { action: 'deny' };
  });
  win.loadURL(url);
}

ipcMain.handle('pick-folder', async () => {
  const res = await dialog.showOpenDialog(win, {
    title: 'Choose a folder for this Loopy project',
    properties: ['openDirectory', 'createDirectory'],
  });
  return res.canceled ? null : res.filePaths[0];
});

ipcMain.handle('open-external', async (_event, target) => {
  if (!target) return false;
  await shell.openExternal(String(target));
  return true;
});

app.whenReady().then(() => {
  // reuse an already-running `ninexf app` (e.g. started from the CLI) if present
  ping(alreadyUp => {
    const ready = () => waitForServer(60, ok => {
      if (!ok) {
        dialog.showErrorBox('Loopy could not start',
          `No server at ${url}.\nLoopy launches a bundled backend executable, so the app bundle may be incomplete.`);
        app.quit();
        return;
      }
      createWindow();
    });
    if (!alreadyUp) {
      startServer(ready);
      return;
    }
    hasCurrentModelList(current => {
      if (current) {
        ready();
        return;
      }
      if (process.env.NINEXF_PORT) {
        dialog.showErrorBox('Loopy backend is stale',
          `A server is already running at ${url}, but it does not include ${REQUIRED_MODEL}.\n` +
          'Stop that server or unset NINEXF_PORT so the desktop app can start a fresh one.');
        app.quit();
        return;
      }
      findOpenPort(DEFAULT_PORT + 1, nextPort => {
        port = nextPort;
        url = `http://127.0.0.1:${port}`;
        startServer(ready);
      });
    });
  });
});

app.on('window-all-closed', () => {
  if (server && spawnedHere) server.kill();
  app.quit();
});
