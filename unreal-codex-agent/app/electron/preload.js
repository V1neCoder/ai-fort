const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    getBackendUrl: () => ipcRenderer.invoke('backend:get-url'),
    getAppInfo: () => ipcRenderer.invoke('backend:get-app-info'),
});
