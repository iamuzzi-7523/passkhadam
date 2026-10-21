const { contextBridge, ipcRenderer } = require('electron');

let initialConfig = { apiUrl: null, isDesktop: true, error: null };
try {
  initialConfig = ipcRenderer.sendSync('get-api-config-sync') || initialConfig;
} catch (e) {
  initialConfig.error = `Failed to retrieve desktop API configuration: ${e.message}`;
}

contextBridge.exposeInMainWorld('PassKhadamDesktop', Object.freeze({
  isDesktop: true,
  config: Object.freeze({ ...initialConfig }),
  getApiConfig: () => Promise.resolve(Object.freeze({ ...initialConfig })),
  getApiConfigSync: () => Object.freeze({ ...initialConfig })
}));
