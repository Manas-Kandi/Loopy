const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const source = path.join(root, 'ninexf');
const targetRoot = path.resolve(__dirname, '..', 'backend');
const target = path.join(targetRoot, 'ninexf');

function filterCopy(src) {
  const base = path.basename(src);
  if (base === '__pycache__' || base === '.DS_Store') return false;
  return true;
}

if (!fs.existsSync(source)) {
  throw new Error(`missing source backend: ${source}`);
}

fs.rmSync(targetRoot, { recursive: true, force: true });
fs.mkdirSync(targetRoot, { recursive: true });
fs.cpSync(source, target, { recursive: true, filter: filterCopy });

const manifest = {
  source,
  copied_at: new Date().toISOString(),
};
fs.writeFileSync(
  path.join(targetRoot, 'manifest.json'),
  `${JSON.stringify(manifest, null, 2)}\n`,
  'utf8',
);

console.log(`Bundled Python backend into ${targetRoot}`);
