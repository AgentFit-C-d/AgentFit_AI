import { getVercelOidcToken } from '@vercel/oidc';
import { timingSafeEqual } from 'node:crypto';

function result(body, status = 200) {
  return Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
}

function matchesSecret(provided, expected) {
  if (typeof provided !== 'string') return false;
  const actualBytes = Buffer.from(provided);
  const expectedBytes = Buffer.from(expected);
  return actualBytes.length === expectedBytes.length && timingSafeEqual(actualBytes, expectedBytes);
}

export function createSearchHandler({ getAccessSecret, getToken, fetchImpl }) {
  return async function search(request) {
    if (request.method !== 'GET') return result({ error: 'METHOD_NOT_ALLOWED' }, 405);

    const accessSecret = getAccessSecret();
    if (typeof accessSecret !== 'string' || !accessSecret) {
      return result({ error: 'PROBE_NOT_CONFIGURED' }, 503);
    }
    if (!matchesSecret(request.headers.get('x-probe-key'), accessSecret)) {
      return result({ error: 'UNAUTHORIZED' }, 401);
    }

    const params = new URL(request.url).searchParams;
    const query = params.get('q')?.trim();
    const limitText = params.get('limit') ?? '10';
    if (!query || query.length < 2 || query.length > 80 || !/^(?:[1-9]|10)$/.test(limitText)) {
      return result({ error: 'INVALID_QUERY' }, 400);
    }
    const limit = Number(limitText);

    let token;
    try {
      token = await getToken();
    } catch {
      return result({ error: 'OIDC_UNAVAILABLE' }, 503);
    }
    if (typeof token !== 'string' || !token) return result({ error: 'OIDC_UNAVAILABLE' }, 503);

    const url = new URL('https://skills.sh/api/v1/skills/search');
    url.searchParams.set('q', query);
    url.searchParams.set('limit', String(limit));
    let response;
    try {
      response = await fetchImpl(url.toString(), {
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
        signal: AbortSignal.timeout(10000),
      });
    } catch {
      return result({ error: 'UPSTREAM_UNAVAILABLE' }, 502);
    }
    if (response.status === 401) return result({ error: 'UPSTREAM_AUTH_FAILED' }, 502);
    if (response.status === 429) return result({ error: 'UPSTREAM_RATE_LIMITED' }, 429);
    if (!response.ok) return result({ error: 'UPSTREAM_UNAVAILABLE' }, 502);

    let payload;
    try {
      payload = await response.json();
    } catch {
      return result({ error: 'INVALID_UPSTREAM_RESPONSE' }, 502);
    }
    if (!payload || !Array.isArray(payload.data) || payload.data.some(
      (item) => !item || typeof item.id !== 'string' || !item.id || typeof item.name !== 'string' || !item.name,
    )) {
      return result({ error: 'INVALID_UPSTREAM_RESPONSE' }, 502);
    }
    const data = payload.data.slice(0, limit).map(({ id, name }) => ({ id, name }));
    return result({
      status: data.length ? 'ok' : 'empty',
      query,
      count: data.length,
      data,
    });
  };
}

export default {
  fetch: createSearchHandler({
    getAccessSecret: () => process.env.PROBE_KEY,
    getToken: getVercelOidcToken,
    fetchImpl: fetch,
  }),
};
