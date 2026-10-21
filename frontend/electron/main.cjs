const { app, BrowserWindow, protocol, net, session, shell, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const url = require('url');

// 1. Register 'app' scheme as privileged before app is ready
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true
    }
  }
]);

// 2. Resolve API Endpoint from runtime config.json or environment
let resolvedApiUrl = null;
let configError = null;

function validateApiUrl(candidate) {
  if (!candidate || typeof candidate !== 'string') {
    return { valid: false, error: 'API URL must be a non-empty string.' };
  }
  try {
    const parsed = new URL(candidate.trim());
    if (parsed.protocol !== 'https:') {
      return { valid: false, error: `Insecure scheme '${parsed.protocol}'. Cloud-Connected Desktop Mode strictly requires an 'https://' endpoint.` };
    }
    const hostLower = (parsed.hostname || '').toLowerCase();
    if (!hostLower || hostLower === 'localhost' || hostLower === '127.0.0.1' || hostLower === '0.0.0.0' || hostLower.endsWith('.local')) {
      return { valid: false, error: `Loopback or local hostnames ('${parsed.hostname}') are rejected in Cloud-Connected Desktop Mode. A live HTTPS backend is required.` };
    }
    if (parsed.username || parsed.password) {
      return { valid: false, error: 'Embedded user credentials in API URL are forbidden.' };
    }
    if (parsed.port && parsed.port !== '443') {
      return { valid: false, error: `Non-standard port ':${parsed.port}' rejected. Cloud HTTPS endpoint must use standard port 443.` };
    }
    if (parsed.search || parsed.hash) {
      return { valid: false, error: 'Query parameters and fragments in API base URL are forbidden.' };
    }
    return { valid: true, url: parsed.origin };
  } catch (e) {
    return { valid: false, error: `Malformed API URL format: ${e.message}` };
  }
}

function resolveRuntimeConfig() {
  const candidatePaths = [];
  try {
    const exeDir = path.dirname(app.getPath('exe'));
    candidatePaths.push(path.join(exeDir, 'config.json'));
  } catch (e) { /* ignore */ }
  candidatePaths.push(path.join(__dirname, '..', 'config.json'));

  for (const configPath of candidatePaths) {
    if (fs.existsSync(configPath)) {
      try {
        const raw = fs.readFileSync(configPath, 'utf8');
        const parsed = JSON.parse(raw);
        if (parsed.apiUrl) {
          const val = validateApiUrl(parsed.apiUrl);
          if (val.valid) {
            resolvedApiUrl = val.url;
            configError = null;
            console.log(`[PassKhadam] Runtime API endpoint resolved from ${configPath}: ${resolvedApiUrl}`);
            return;
          } else {
            configError = `Configuration error in ${configPath}: ${val.error}`;
            resolvedApiUrl = null;
            console.error(`[PassKhadam] ${configError}`);
            return;
          }
        } else {
          configError = `Missing 'apiUrl' property in ${configPath}. A valid https:// endpoint is required.`;
          resolvedApiUrl = null;
          return;
        }
      } catch (err) {
        configError = `Failed to parse ${configPath}: ${err.message}`;
        resolvedApiUrl = null;
        return;
      }
    }
  }

  // Check PASSKHADAM_API_URL environment variable
  const envUrl = process.env.PASSKHADAM_API_URL;
  if (envUrl) {
    const val = validateApiUrl(envUrl);
    if (val.valid) {
      resolvedApiUrl = val.url;
      configError = null;
      console.log(`[PassKhadam] Runtime API endpoint resolved from PASSKHADAM_API_URL: ${resolvedApiUrl}`);
      return;
    } else {
      configError = `Invalid PASSKHADAM_API_URL environment variable: ${val.error}`;
      resolvedApiUrl = null;
      console.error(`[PassKhadam] ${configError}`);
      return;
    }
  }

  // Default production cloud backend if unconfigured
  const DEFAULT_CLOUD_API = 'https://passkhadam-api.onrender.com';
  const defaultVal = validateApiUrl(DEFAULT_CLOUD_API);
  if (defaultVal.valid) {
    resolvedApiUrl = defaultVal.url;
    configError = null;
    console.log(`[PassKhadam] Default production cloud endpoint active: ${resolvedApiUrl}`);
  } else {
    configError = 'No valid HTTPS API endpoint configured.';
    resolvedApiUrl = null;
  }
}

// 3. Complete Authority & Canonical Path Containment Custom Protocol Handler
function registerCustomProtocol(appDistDir) {
  const canonicalBaseDir = fs.realpathSync(path.resolve(appDistDir));

  protocol.handle('app', async (request) => {
    try {
      // Method check: Only GET and HEAD permitted
      if (request.method !== 'GET' && request.method !== 'HEAD') {
        return new Response('Method Not Allowed', { status: 405 });
      }

      const requestUrl = new URL(request.url);

      // Strict Complete Authority Validation:
      // - Protocol must be strictly 'app:'
      // - Hostname must equal 'passkhadam.app' exactly
      // - Host must equal 'passkhadam.app' (blocks unexpected ports)
      // - Port must be empty
      // - Username & password must be empty (blocks userinfo credentials)
      if (
        requestUrl.protocol !== 'app:' ||
        requestUrl.hostname !== 'passkhadam.app' ||
        requestUrl.host !== 'passkhadam.app' ||
        requestUrl.port !== '' ||
        requestUrl.username !== '' ||
        requestUrl.password !== ''
      ) {
        return new Response('Forbidden: Untrusted Authority, Unexpected Port, or Credentials Detected', { status: 403 });
      }

      let decodedPath = decodeURIComponent(requestUrl.pathname);

      // Default index route for SPA entry
      if (decodedPath === '/' || decodedPath === '') {
        decodedPath = '/index.html';
      }

      // Reject Null Bytes & UNC / Windows Device Paths
      if (decodedPath.includes('\0')) {
        return new Response('Bad Request: Null Byte Detected', { status: 400 });
      }
      if (/^[/\\]{2}/.test(decodedPath) || /^[a-zA-Z]:/.test(decodedPath) || /[\\/]?[.]+[\\/]/.test(decodedPath)) {
        return new Response('Forbidden: Invalid Path Structure', { status: 403 });
      }

      // Sanitize relative path and resolve against canonicalBaseDir
      const sanitizedRelative = decodedPath.replace(/^[/\\]+/, '');
      const candidatePath = path.resolve(canonicalBaseDir, sanitizedRelative);

      if (!fs.existsSync(candidatePath)) {
        // SPA Fallback: If route has no file extension (client-side route), serve index.html
        if (!path.extname(candidatePath)) {
          const indexPath = path.resolve(canonicalBaseDir, 'index.html');
          if (fs.existsSync(indexPath)) {
            return net.fetch(url.pathToFileURL(indexPath).toString());
          }
        }
        return new Response('Not Found', { status: 404 });
      }

      // Canonical target resolution (resolves symlinks)
      const realTarget = fs.realpathSync(candidatePath);

      // Robust Path Containment Verification via path.relative()
      const relative = path.relative(canonicalBaseDir, realTarget);
      const isContained = relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));

      if (!isContained) {
        return new Response('Forbidden: Directory Traversal Blocked', { status: 403 });
      }

      return net.fetch(url.pathToFileURL(realTarget).toString());
    } catch (err) {
      return new Response('Bad Request: Invalid Request Format', { status: 400 });
    }
  });
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 700,
    title: 'PASSKHADAM — Portable Worker Identity',
    backgroundColor: '#020617',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      preload: path.join(__dirname, 'preload.cjs')
    }
  });

  // Strict In-App Navigation Restriction: Exact trusted origin match required
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    try {
      const parsed = new URL(navigationUrl);
      const isTrustedAppOrigin =
        parsed.protocol === 'app:' &&
        parsed.hostname === 'passkhadam.app' &&
        parsed.host === 'passkhadam.app' &&
        parsed.port === '' &&
        parsed.username === '' &&
        parsed.password === '';

      if (!isTrustedAppOrigin) {
        event.preventDefault();
      }
    } catch {
      event.preventDefault();
    }
  });

  // Strict External Link Window Handler
  mainWindow.webContents.setWindowOpenHandler(({ url: targetUrl }) => {
    try {
      const parsed = new URL(targetUrl);
      const ALLOWED_EXTERNAL_HOSTS = new Set([
        'passkhadam.vercel.app',
        'sepolia.etherscan.io'
      ]);
      if (
        parsed.protocol === 'https:' &&
        ALLOWED_EXTERNAL_HOSTS.has(parsed.hostname) &&
        parsed.port === '' &&
        parsed.username === '' &&
        parsed.password === ''
      ) {
        shell.openExternal(targetUrl);
      }
    } catch {}
    return { action: 'deny' };
  });

  // Load the application entry point via custom protocol
  mainWindow.loadURL('app://passkhadam.app/index.html');
}

app.whenReady().then(() => {
  resolveRuntimeConfig();

  // IPC Handlers for exposing runtime API configuration to renderer (read-only validation)
  ipcMain.handle('get-api-config', () => {
    return {
      apiUrl: resolvedApiUrl,
      error: configError,
      isDesktop: true
    };
  });

  ipcMain.on('get-api-config-sync', (event) => {
    event.returnValue = {
      apiUrl: resolvedApiUrl,
      error: configError,
      isDesktop: true
    };
  });

  // Strict CSP Headers Injection
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const connectOrigins = ["'self'", "app:"];
    if (resolvedApiUrl) {
      connectOrigins.push(resolvedApiUrl);
    }
    connectOrigins.push(
      "https://identitytoolkit.googleapis.com",
      "https://securetoken.googleapis.com",
      "https://gateway.pinata.cloud"
    );

    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          `default-src 'self' app:; script-src 'self' app: https://apis.google.com https://www.gstatic.com; style-src 'self' app: 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' app: https://fonts.gstatic.com data:; connect-src ${connectOrigins.join(' ')}; img-src 'self' app: data: blob: https://gateway.pinata.cloud; frame-src https://*.firebaseapp.com; object-src 'none'; base-uri 'self';`
        ]
      }
    });
  });

  const distDir = path.join(__dirname, '..', 'dist');
  registerCustomProtocol(distDir);

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
