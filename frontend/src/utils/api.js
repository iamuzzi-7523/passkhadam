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
 * Formats a raw or partially typed Aadhaar string into standard 4-digit grouped format:
 * "XXXX XXXX XXXX" (up to 14 characters total: 12 digits + 2 spaces).
 * Non-digit characters are filtered out.
 *
 * @param {string|number} value
 * @returns {string} Formatted Aadhaar string with spaces
 */
export function formatAadhaarInput(value) {
  if (!value) return '';
  const digits = String(value).replace(/\D/g, '').slice(0, 12);
  const parts = [];
  for (let i = 0; i < digits.length; i += 4) {
    parts.push(digits.slice(i, i + 4));
  }
  return parts.join(' ');
}

/**
 * Extracts raw numeric digits from any Aadhaar input, stripping all spaces and separators.
 *
 * @param {string|number} value
 * @returns {string} Clean numeric string of digits (max 12)
 */
export function cleanAadhaarDigits(value) {
  if (!value) return '';
  return String(value).replace(/\D/g, '').slice(0, 12);
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

/**
 * Fetches the worker's immutable employment history ledger.
 * Calls GET /api/v1/worker/employment-history/me with fallback to /wallet/me.
 * 
 * @returns {Promise<{worker_did: string, employments: Array, active_count: number, historical_count: number}>}
 */
export async function getEmploymentHistory() {
  try {
    const res = await apiFetch('/api/v1/worker/employment-history/me');
    if (res.ok) {
      return await res.json();
    }
  } catch (e) {
    console.warn('Dedicated employment history endpoint unavailable, falling back to wallet', e);
  }

  // Graceful fallback to wallet
  const walletRes = await apiFetch('/api/v1/worker/wallet/me');
  if (!walletRes.ok) {
    throw new Error('Failed to fetch employment history');
  }
  const walletData = await walletRes.json();
  const emps = walletData.employments || [];
  const active = emps.filter(e => (e.status || '').toUpperCase() === 'ACTIVE');
  const hist = emps.filter(e => (e.status || '').toUpperCase() !== 'ACTIVE');
  return {
    worker_did: walletData.worker_did,
    employments: emps,
    active_count: active.length,
    historical_count: hist.length
  };
}

/**
 * Updates worker profile fields (skills, worker_category, current_state, address, etc.)
 * Calls PUT /api/v1/worker/profile/me.
 * 
 * @param {Object} updatePayload - Fields to update { worker_category, skills, current_state, address, etc. }
 * @returns {Promise<Object>} Updated profile response
 */
export async function updateWorkerProfile(updatePayload) {
  const res = await apiFetch('/api/v1/worker/profile/me', {
    method: 'PUT',
    body: updatePayload
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to update worker profile');
  }
  return data;
}

/**
 * Convenience helper to update worker trade category and skills.
 * 
 * @param {string} workerCategory - Main trade or custom profession
 * @param {string[]} skills - Array of skill strings
 * @returns {Promise<Object>}
 */
export async function updateWorkerSkills(workerCategory, skills) {
  try {
    const res = await apiFetch('/api/v1/worker/skills/me', {
      method: 'PUT',
      body: {
        worker_category: workerCategory,
        skills: skills
      }
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (e) {
    console.warn('Dedicated skills update endpoint failed, falling back to profile', e);
  }
  return updateWorkerProfile({
    worker_category: workerCategory,
    skills: skills
  });
}

export default apiFetch;
