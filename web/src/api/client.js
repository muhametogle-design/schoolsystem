/**
 * Thin JSON client for the FastAPI backend.
 *
 * Two auth mechanisms are sent on every call: the bearer token (primary) and
 * an HttpOnly cookie via `credentials: 'include'` (fallback). The cookie is
 * what keeps sessions alive behind reverse proxies, embedded frames, and
 * privacy-focused browsers that do not allow localStorage.
 */
const TOKEN_KEY = 'ne_emis_token';
const USER_KEY = 'ne_emis_user';

function storage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readStorage(key) {
  try {
    return storage()?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    const store = storage();
    if (!store) return false;
    store.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function removeStorage(key) {
  try {
    storage()?.removeItem(key);
  } catch {
    // The HttpOnly cookie remains available as the session fallback.
  }
}

export const getToken = () => readStorage(TOKEN_KEY);

export const setToken = (token) => {
  if (token) writeStorage(TOKEN_KEY, token);
  else removeStorage(TOKEN_KEY);
};

export const getStoredUser = () => {
  try {
    const raw = readStorage(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const setStoredUser = (user) => {
  if (user) writeStorage(USER_KEY, JSON.stringify(user));
  else removeStorage(USER_KEY);
};

export const clearStoredUser = () => removeStorage(USER_KEY);

export async function api(path, { method = 'GET', body } = {}) {
  const token = getToken();
  // Module 3: tell the backend the request prefers minimal payloads when the
  // low-bandwidth Data Saver mode is resolved active.
  const dataSaver = (() => {
    try {
      return document.documentElement.dataset.saver === '1';
    } catch {
      return false;
    }
  })();
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(dataSaver ? { 'X-Data-Saver': '1', 'Save-Data': 'on' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = {};
  try {
    data = await res.json();
  } catch {
    /* empty body — leave data as {} */
  }

  if (!res.ok) {
    // A background cookie/session probe can finish after a new sign-in. Only
    // clear storage if this response still belongs to the token it sent.
    if (res.status === 401 && token && getToken() === token) {
      setToken(null);
      clearStoredUser();
      window.dispatchEvent(new CustomEvent('ne-emis:session-expired'));
    }
    const detail =
      typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data);
    const error = new Error(detail || `HTTP ${res.status}`);
    error.status = res.status;
    throw error;
  }
  return data;
}

/** Query-string builder that skips null/undefined/empty values. */
export function qs(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') search.append(key, value);
  });
  const str = search.toString();
  return str ? `?${str}` : '';
}
