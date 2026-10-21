/**
 * Centralized API Fetch & Data Sanitization Utilities
 * PassKhadam v0.4 Architecture
 */

/**
 * Format any raw, space-separated, or unformatted masked Aadhaar into
 * strict XXXX-XXXX-1234 format.
 *
 * @param {string|number} raw - The raw Aadhaar or masked string
 * @returns {string} Formatted masked Aadhaar or empty string
 */
export function formatMaskedAadhaar(raw) {
  if (!raw) return '';
  const str = String(raw).trim();
  const clean = str.replace(/[\s-]/g, '');

  if (clean.length === 12) {
    const last4 = clean.slice(-4);
    return `XXXX-XXXX-${last4}`;
  }

  const match = str.match(/(\d{4})$/);
  if (match) {
    return `XXXX-XXXX-${match[1]}`;
  }

  return str;
}

/**
 * Resolves desktop configuration synchronously or asynchronously from Electron preload bridge.
 */
export function getDesktopConfig() {
  if (typeof window !== 'undefined' && window.PassKhadamDesktop?.config) {
    return window.PassKhadamDesktop.config;
  }
  return { apiUrl: '', isDesktop: false, error: null };
}

export function getApiBase() {
  if (typeof window !== 'undefined' && window.PassKhadamDesktop?.config?.apiUrl) {
    return window.PassKhadamDesktop.config.apiUrl;
  }
  return '';
}

export async function getDesktopApiConfig() {
  return getDesktopConfig();
}

export function getApiBaseSync() {
  return getApiBase();
}

/**
 * Centralized fetch client that automatically injects Bearer token
 * from localStorage ('pk_token') and JSON headers when applicable.
 *
 * @param {string} endpoint - API path or full URL
 * @param {RequestInit} [options={}] - Standard fetch options
 * @returns {Promise<Response>} Fetch Response object
 */
export async function apiFetch(endpoint, options = {}) {
  const cfg = await getDesktopApiConfig();
  if (cfg.isDesktop && cfg.error) {
    throw new Error(`Cloud-Connected Desktop Mode Error: ${cfg.error}`);
  }

  const { headers = {}, body, ...restOptions } = options;
  const mergedHeaders = { ...headers };

  // Retrieve auth token from localStorage if not manually set
  const token = localStorage.getItem('pk_token');
  if (token && !mergedHeaders['Authorization'] && !mergedHeaders['authorization']) {
    mergedHeaders['Authorization'] = `Bearer ${token}`;
  }

  let finalBody = body;
  // Automatically serialize objects to JSON unless already string, FormData, or Blob
  if (
    body &&
    typeof body === 'object' &&
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    !(body instanceof URLSearchParams)
  ) {
    if (!mergedHeaders['Content-Type'] && !mergedHeaders['content-type']) {
      mergedHeaders['Content-Type'] = 'application/json';
    }
    finalBody = JSON.stringify(body);
  }

  let targetUrl = endpoint;
  if (cfg.isDesktop && cfg.apiUrl && typeof endpoint === 'string' && endpoint.startsWith('/')) {
    targetUrl = `${cfg.apiUrl}${endpoint}`;
  }

  return fetch(targetUrl, {
    ...restOptions,
    headers: mergedHeaders,
    body: finalBody,
  });
}

export default apiFetch;
