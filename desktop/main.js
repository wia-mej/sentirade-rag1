const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1300,
        height: 850,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    mainWindow.loadFile('ui/index.html');

    // IPC Handlers
    ipcMain.on('minimize-window', () => {
        if (mainWindow) mainWindow.minimize();
    });

    ipcMain.on('maximize-window', () => {
        if (mainWindow) {
            if (mainWindow.isMaximized()) {
                mainWindow.unmaximize();
            } else {
                mainWindow.maximize();
            }
        }
    });

    ipcMain.on('close-window', () => {
        if (mainWindow) mainWindow.close();
    });

    // Open DevTools in development
    // mainWindow.webContents.openDevTools();
}

function startBackend() {
    const isWindows = process.platform === 'win32';
    const venvPath = isWindows
        ? path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe')
        : path.join(__dirname, '..', 'venv', 'bin', 'python');
    const apiPath = path.join(__dirname, '..', 'api.py');

    console.log(`Starting backend from: ${apiPath}`);

    pythonProcess = spawn(venvPath, [apiPath], {
        cwd: path.join(__dirname, '..')
    });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`Backend: ${data}`);
        if (mainWindow) {
            mainWindow.webContents.send('backend-status', { status: 'connected' });
        }
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`Backend Error: ${data}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Backend process exited with code ${code}`);
        if (mainWindow) {
            mainWindow.webContents.send('backend-status', { status: 'disconnected', code });
        }
        // Attempt to restart after a delay
        setTimeout(() => {
            console.log('Attempting to restart backend...');
            if (mainWindow) {
                mainWindow.webContents.send('backend-status', { status: 'reconnecting' });
            }
            startBackend();
        }, 5000);
    });

    pythonProcess.on('error', (err) => {
        console.error('Failed to start backend process:', err);
        if (mainWindow) {
            mainWindow.webContents.send('backend-status', { status: 'error', error: err.message });
        }
    });
}

app.whenReady().then(() => {
    startBackend();
    createWindow();

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') {
        if (pythonProcess) {
            pythonProcess.removeAllListeners('close'); // Prevent restart loop on exit
            pythonProcess.kill();
        }
        app.quit();
    }
});

app.on('before-quit', () => {
    if (pythonProcess) pythonProcess.kill();
});
