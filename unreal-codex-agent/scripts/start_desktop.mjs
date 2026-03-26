import { spawn } from 'node:child_process';
import http from 'node:http';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const workspaceRoot = path.resolve(__dirname, '..');
const frontendDir = path.join(workspaceRoot, 'app', 'frontend');
const electronDir = path.join(workspaceRoot, 'app', 'electron');
const frontendUrl = process.env.ELECTRON_FRONTEND_URL || 'http://127.0.0.1:3000';

let frontendProcess = null;
let electronProcess = null;

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function isPortOpen(port, host = '127.0.0.1') {
  return new Promise(resolve => {
    const socket = net.createConnection({ port, host });
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('error', () => resolve(false));
  });
}

function requestText(url) {
    return new Promise(resolve => {
        const req = http.get(url, response => {
            let body = '';
            response.setEncoding('utf8');
            response.on('data', chunk => {
              body += chunk;
            });
            response.resume();
            response.on('end', () => {
              resolve({
                ok: Boolean(response.statusCode && response.statusCode < 500),
                statusCode: response.statusCode || 0,
                body,
              });
            });
        });
        req.setTimeout(2000, () => {
          req.destroy();
          resolve({ ok: false, statusCode: 0, body: '' });
        });
        req.once('error', () => resolve({ ok: false, statusCode: 0, body: '' }));
    });
}

async function waitForFrontend(url, attempts = 90) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const response = await requestText(url);
    if (response.ok && response.body.includes('<title>UEFN Codex Agent</title>')) {
      return true;
    }
    await delay(1000);
  }
  return false;
}

function spawnLogged(command, args, options, prefix) {
  const child = spawn(command, args, options);
  child.stdout?.on('data', chunk => {
    const text = String(chunk).trim();
    if (text) {
      console.log(`[${prefix}] ${text}`);
    }
  });
  child.stderr?.on('data', chunk => {
    const text = String(chunk).trim();
    if (text) {
      console.error(`[${prefix}] ${text}`);
    }
  });
  return child;
}

function stopChild(child) {
  if (!child || child.killed) {
    return;
  }
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], {
      windowsHide: true,
      stdio: 'ignore',
    });
    return;
  }
  child.kill('SIGTERM');
}

async function ensureFrontend() {
  const frontendPort = 3000;
  const portOpen = await isPortOpen(frontendPort);
  if (portOpen) {
    const response = await requestText(frontendUrl);
    if (response.ok && response.body.includes('<title>UEFN Codex Agent</title>')) {
      console.log(`[desktop] Reusing frontend at ${frontendUrl}`);
      return;
    }
    throw new Error(`Port 3000 is already in use by a different app. Close it or free port 3000, then retry.`);
  }

  console.log('[desktop] Starting frontend dev server...');
  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  frontendProcess = spawnLogged(
    npmCommand,
    ['start'],
    {
      cwd: frontendDir,
      env: {
        ...process.env,
        BROWSER: 'none',
        PORT: '3000',
      },
      windowsHide: false,
      stdio: ['ignore', 'pipe', 'pipe'],
    },
    'frontend',
  );

  const ready = await waitForFrontend(frontendUrl);
  if (!ready) {
    throw new Error(`Frontend did not become ready at ${frontendUrl}`);
  }
}

async function startElectron() {
  console.log('[desktop] Starting Electron...');
  const electronCli = path.join(electronDir, 'node_modules', 'electron', 'cli.js');

  electronProcess = spawnLogged(
    process.execPath,
    [electronCli, electronDir],
    {
      cwd: workspaceRoot,
      env: {
        ...process.env,
        ELECTRON_FRONTEND_URL: frontendUrl,
      },
      windowsHide: false,
      stdio: ['ignore', 'pipe', 'pipe'],
    },
    'electron',
  );

  electronProcess.on('exit', code => {
    if (code && code !== 0) {
      console.error(`[desktop] Electron exited with code ${code}`);
    }
    stopChild(frontendProcess);
    process.exit(code ?? 0);
  });
}

function installSignalHandlers() {
  const shutdown = () => {
    stopChild(electronProcess);
    stopChild(frontendProcess);
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
  process.on('exit', shutdown);
}

async function main() {
  installSignalHandlers();
  await ensureFrontend();
  await startElectron();
}

main().catch(error => {
  console.error('[desktop] Startup failed:', error.message || error);
  stopChild(electronProcess);
  stopChild(frontendProcess);
  process.exit(1);
});
