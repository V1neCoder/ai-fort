const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const net = require('net');
const path = require('path');

const FRONTEND_URL = process.env.ELECTRON_FRONTEND_URL || 'http://localhost:3000';
const WORKSPACE_ROOT = path.resolve(__dirname, '..', '..');
const PRELOAD_PATH = path.join(__dirname, 'preload.js');
const BACKEND_ENTRY = path.join(WORKSPACE_ROOT, 'app', 'backend', 'server.py');
const BACKEND_HOST = '127.0.0.1';
const BACKEND_PORT_START = 8000;
const BACKEND_PORT_END = 8035;

let mainWindow = null;
let backendProcess = null;
let backendUrl = '';
let backendPromise = null;
let lastBackendFailure = '';
const backendLogTail = [];

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function pushBackendLog(prefix, chunk) {
    const text = String(chunk || '').trim();
    if (!text) {
        return;
    }
    backendLogTail.push(`[${prefix}] ${text}`);
    if (backendLogTail.length > 30) {
        backendLogTail.splice(0, backendLogTail.length - 30);
    }
}

function resolvePythonLaunchers() {
    const launchers = [];
    const bundledVenv = path.join(WORKSPACE_ROOT, '.venv', 'Scripts', 'python.exe');
    if (fs.existsSync(bundledVenv)) {
        launchers.push({ command: bundledVenv, args: [BACKEND_ENTRY], label: bundledVenv });
    }

    const explicitPython = process.env.PYTHON;
    if (explicitPython && fs.existsSync(explicitPython)) {
        launchers.push({ command: explicitPython, args: [BACKEND_ENTRY], label: explicitPython });
    }

    launchers.push({ command: 'python', args: [BACKEND_ENTRY], label: 'python' });
    if (process.platform === 'win32') {
        launchers.push({ command: 'py', args: ['-3', BACKEND_ENTRY], label: 'py -3' });
    }
    return launchers;
}

function requestJson(url) {
    return new Promise((resolve, reject) => {
        const req = http.get(url, response => {
            let body = '';
            response.setEncoding('utf8');

            response.on('data', chunk => {
                body += chunk;
            });

            response.on('end', () => {
                if (response.statusCode !== 200) {
                    reject(new Error(`HTTP ${response.statusCode} from ${url}`));
                    return;
                }

                try {
                    resolve(JSON.parse(body));
                } catch (error) {
                    reject(error);
                }
            });
        });

        req.setTimeout(2500, () => {
            req.destroy(new Error(`Timed out waiting for ${url}`));
        });

        req.on('error', reject);
    });
}

async function probeBackend(port) {
    try {
        const payload = await requestJson(`http://${BACKEND_HOST}:${port}/api/ping`);
        const compatibleVersion = typeof payload?.api_version === 'string'
            && Number.parseFloat(payload.api_version) >= 2.4;
        return {
            reachable: true,
            compatible: payload?.features?.chat_sessions === true
                && payload?.features?.attachment_previews === true
                && payload?.features?.structured_local_vision === true
                && payload?.features?.fast_startup_ping === true
                && compatibleVersion,
            payload,
        };
    } catch {
        return {
            reachable: false,
            compatible: false,
            payload: null,
        };
    }
}

function isPortFree(port) {
    return new Promise(resolve => {
        const tester = net.createServer();

        tester.once('error', () => {
            resolve(false);
        });

        tester.once('listening', () => {
            tester.close(() => resolve(true));
        });

        tester.listen(port, BACKEND_HOST);
    });
}

async function allocateBackendPort() {
    for (let port = BACKEND_PORT_START; port <= BACKEND_PORT_END; port += 1) {
        const free = await isPortFree(port);
        if (free) {
            return { port, needsSpawn: true };
        }

        const health = await probeBackend(port);
        if (health.compatible) {
            return { port, needsSpawn: false };
        }
    }

    throw new Error(`Could not find a usable backend port between ${BACKEND_PORT_START} and ${BACKEND_PORT_END}`);
}

async function waitForBackendReady(port, child) {
    const url = `http://${BACKEND_HOST}:${port}`;

    for (let attempt = 0; attempt < 80; attempt += 1) {
        if (child && child.exitCode !== null) {
            const details = lastBackendFailure || backendLogTail.join('\n');
            throw new Error(`Backend exited before becoming ready (code ${child.exitCode})${details ? `\n${details}` : ''}`);
        }

        const health = await probeBackend(port);
        if (health.compatible) {
            return url;
        }

        await delay(500);
    }

    const details = lastBackendFailure || backendLogTail.join('\n');
    throw new Error(`Backend did not become ready on ${url}${details ? `\n${details}` : ''}`);
}

function stopBackendProcess() {
    if (!backendProcess || backendProcess.killed) {
        return;
    }

    const pid = backendProcess.pid;
    backendProcess = null;

    if (process.platform === 'win32' && pid) {
        spawn('taskkill', ['/pid', String(pid), '/t', '/f'], {
            windowsHide: true,
            stdio: 'ignore',
        });
        return;
    }

    try {
        process.kill(pid, 'SIGTERM');
    } catch {
        // Process already exited.
    }
}

async function ensureBackend() {
    if (backendUrl) {
        return backendUrl;
    }

    if (backendPromise) {
        return backendPromise;
    }

    backendPromise = (async () => {
        const { port, needsSpawn } = await allocateBackendPort();
        const url = `http://${BACKEND_HOST}:${port}`;

        if (!needsSpawn) {
            backendUrl = url;
            console.log(`[electron] Reusing compatible backend at ${backendUrl}`);
            return backendUrl;
        }

        const launchers = resolvePythonLaunchers();
        let lastError = null;

        for (const python of launchers) {
            backendLogTail.length = 0;
            lastBackendFailure = '';
            const child = spawn(python.command, python.args, {
                cwd: WORKSPACE_ROOT,
                env: {
                    ...process.env,
                    BACKEND_HOST,
                    BACKEND_PORT: String(port),
                    PYTHONUNBUFFERED: '1',
                },
                windowsHide: true,
                stdio: ['ignore', 'pipe', 'pipe'],
            });

            backendProcess = child;

            child.stdout?.on('data', chunk => {
                pushBackendLog(`backend:${port}:stdout`, chunk);
                const text = String(chunk).trim();
                if (text) {
                    console.log(`[backend:${port}] ${text}`);
                }
            });

            child.stderr?.on('data', chunk => {
                pushBackendLog(`backend:${port}:stderr`, chunk);
                const text = String(chunk).trim();
                if (text) {
                    console.error(`[backend:${port}] ${text}`);
                    lastBackendFailure = text;
                }
            });

            child.on('exit', (code, signal) => {
                console.log(`[electron] Backend exited (code=${code}, signal=${signal || 'none'})`);
                if (backendProcess && child.pid === backendProcess.pid) {
                    backendProcess = null;
                    backendUrl = '';
                    backendPromise = null;
                }
            });

            child.on('error', error => {
                const detail = `[spawn] ${python.label}: ${error.message || error}`;
                pushBackendLog(`backend:${port}:spawn`, detail);
                lastBackendFailure = detail;
                console.error('[electron] Backend spawn failed:', error);
            });

            try {
                backendUrl = await waitForBackendReady(port, child);
                console.log(`[electron] Backend ready at ${backendUrl}`);
                return backendUrl;
            } catch (error) {
                lastError = error;
                const failedChild = backendProcess;
                if (failedChild && failedChild.pid === child.pid) {
                    stopBackendProcess();
                }
            }
        }

        throw lastError || new Error('Backend could not be launched by any configured Python launcher.');
    })();

    try {
        return await backendPromise;
    } catch (error) {
        backendPromise = null;
        backendUrl = '';
        throw error;
    }
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1600,
        height: 1000,
        minWidth: 1000,
        minHeight: 700,
        title: 'UEFN Codex Agent',
        autoHideMenuBar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: PRELOAD_PATH,
        },
    });

    void tryLoad();
}

async function tryLoad(attempt = 0) {
    try {
        await mainWindow.loadURL(FRONTEND_URL);
    } catch (error) {
        if (attempt < 30) {
            await delay(1000);
            return tryLoad(attempt + 1);
        }

        console.error('Could not connect to frontend at', FRONTEND_URL, error);
    }
}

ipcMain.handle('backend:get-url', async () => ensureBackend());

ipcMain.handle('backend:get-app-info', async () => ({
    backendUrl: await ensureBackend(),
    frontendUrl: FRONTEND_URL,
    workspaceRoot: WORKSPACE_ROOT,
    electronVersion: process.versions.electron,
    chromeVersion: process.versions.chrome,
}));

app.whenReady().then(() => {
    createWindow();
    void ensureBackend().catch(error => {
        console.error('[electron] Backend startup failed:', error);
    });
});

app.on('before-quit', () => {
    stopBackendProcess();
});

app.on('window-all-closed', () => {
    app.quit();
});
