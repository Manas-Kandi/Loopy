const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..', '..');
const appRoot = path.resolve(__dirname, '..');
const distPath = path.join(appRoot, 'backend-bin');
const workPath = path.join(appRoot, '.pyinstaller');
const entryPoint = path.join(root, 'ninexf', '__main__.py');

function findPython() {
  const candidates = [
    process.env.LOOPY_BUILD_PYTHON,
    'python3.11',
    'python3.12',
    'python3',
  ].filter(Boolean);
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ['--version'], { encoding: 'utf8' });
    if (result.status === 0) return candidate;
  }
  throw new Error('Could not find Python for building the Loopy backend');
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    env: {
      ...process.env,
      PYTHONPATH: root,
      ...(options.env || {}),
    },
    cwd: root,
  });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with exit code ${result.status}`);
  }
}

const python = findPython();
fs.rmSync(distPath, { recursive: true, force: true });
fs.mkdirSync(distPath, { recursive: true });

run(python, [
  '-m',
  'PyInstaller',
  '--clean',
  '--noconfirm',
  '--onefile',
  '--name',
  'loopy-backend',
  '--distpath',
  distPath,
  '--workpath',
  workPath,
  '--specpath',
  workPath,
  entryPoint,
]);

console.log(`Built standalone backend at ${path.join(distPath, 'loopy-backend')}`);
