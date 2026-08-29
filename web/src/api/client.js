/**
 * Thin JSON client for the FastAPI backend.
 *
 * Two auth mechanisms are sent on every call: the bearer token (primary) and
 * an HttpOnly cookie via `credentials: 'include'` (fallback). The cookie is
 * what keeps sessions alive behind reverse proxies and embedded frames that
 * strip the Authorization header.
 */
const TOKEN_KEY = 'ne_emis_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export const setToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

export async function api(path, { method = 'GET', body } = {}) {
  const token = getToken();
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    if (res.status === 401 && token) {
      setToken(null);
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
