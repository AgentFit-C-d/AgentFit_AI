import assert from 'node:assert/strict';
import test from 'node:test';

const { createSearchHandler } = await import('../api/search.js');

const skill = {
  id: 'expo/skills/react-native',
  slug: 'react-native',
  name: 'React Native',
  source: 'expo/skills',
  installs: 3842,
  sourceType: 'github',
  installUrl: 'https://github.com/expo/skills',
  url: 'https://skills.sh/expo/skills/react-native',
};

function request(query = 'react%20native&limit=2', key = 'probe-secret') {
  return new Request(`https://probe.example/api/search?q=${query}`, {
    headers: key === null ? {} : { 'x-probe-key': key },
  });
}

test('uses the request token to return only limited skill identifiers', async () => {
  const calls = [];
  const handler = createSearchHandler({
    getAccessSecret: () => 'probe-secret',
    getToken: async () => 'oidc-secret',
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return Response.json({ data: [skill], query: 'react native', count: 1 });
    },
  });

  const response = await handler(request());

  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.deepEqual(await response.json(), {
    status: 'ok',
    query: 'react native',
    count: 1,
    data: [{ id: 'expo/skills/react-native', name: 'React Native' }],
  });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://skills.sh/api/v1/skills/search?q=react+native&limit=2');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer oidc-secret');
});

test('reports a successful search with no candidates as empty', async () => {
  const handler = createSearchHandler({
    getAccessSecret: () => 'probe-secret',
    getToken: async () => 'oidc-secret',
    fetchImpl: async () => Response.json({ data: [], query: 'react native', count: 0 }),
  });

  const response = await handler(request());

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    status: 'empty',
    query: 'react native',
    count: 0,
    data: [],
  });
});

test('reports missing OIDC without calling the external API', async () => {
  let fetchCount = 0;
  const handler = createSearchHandler({
    getAccessSecret: () => 'probe-secret',
    getToken: async () => { throw new Error('token details must stay private'); },
    fetchImpl: async () => { fetchCount += 1; },
  });

  const response = await handler(request());

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: 'OIDC_UNAVAILABLE' });
  assert.equal(fetchCount, 0);
});

test('rejects an unauthorized caller before requesting a token', async () => {
  let tokenCount = 0;
  let fetchCount = 0;
  const handler = createSearchHandler({
    getAccessSecret: () => 'probe-secret',
    getToken: async () => { tokenCount += 1; return 'oidc-secret'; },
    fetchImpl: async () => { fetchCount += 1; },
  });

  const response = await handler(request('react&limit=2', null));

  assert.equal(response.status, 401);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.deepEqual(await response.json(), { error: 'UNAUTHORIZED' });
  assert.equal(tokenCount, 0);
  assert.equal(fetchCount, 0);
});

test('does not search when the probe secret is not configured', async () => {
  let tokenCount = 0;
  const handler = createSearchHandler({
    getAccessSecret: () => '',
    getToken: async () => { tokenCount += 1; return 'oidc-secret'; },
    fetchImpl: async () => { throw new Error('external search must not run'); },
  });

  const response = await handler(request());

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: 'PROBE_NOT_CONFIGURED' });
  assert.equal(tokenCount, 0);
});

test('rejects invalid queries and oversized result limits before external calls', async () => {
  let tokenCount = 0;
  const handler = createSearchHandler({
    getAccessSecret: () => 'probe-secret',
    getToken: async () => { tokenCount += 1; return 'oidc-secret'; },
    fetchImpl: async () => { throw new Error('external search must not run'); },
  });

  for (const query of ['a&limit=2', 'react&limit=11', 'react&limit=1.5', 'react&limit=0', `${'a'.repeat(81)}&limit=2`]) {
    const response = await handler(request(query));
    assert.equal(response.status, 400, query);
    assert.deepEqual(await response.json(), { error: 'INVALID_QUERY' });
  }
  assert.equal(tokenCount, 0);
});

test('accepts only GET without requesting a token for other methods', async () => {
  let tokenCount = 0;
  const handler = createSearchHandler({
    getAccessSecret: () => 'probe-secret',
    getToken: async () => { tokenCount += 1; return 'oidc-secret'; },
    fetchImpl: async () => { throw new Error('external search must not run'); },
  });

  const response = await handler(new Request('https://probe.example/api/search?q=react', {
    method: 'POST',
    headers: { 'x-probe-key': 'probe-secret' },
  }));

  assert.equal(response.status, 405);
  assert.deepEqual(await response.json(), { error: 'METHOD_NOT_ALLOWED' });
  assert.equal(tokenCount, 0);
});

test('normalizes upstream HTTP errors without leaking response bodies or tokens', async () => {
  for (const [upstreamStatus, expectedStatus, expectedError] of [
    [401, 502, 'UPSTREAM_AUTH_FAILED'],
    [429, 429, 'UPSTREAM_RATE_LIMITED'],
    [503, 502, 'UPSTREAM_UNAVAILABLE'],
  ]) {
    const handler = createSearchHandler({
      getAccessSecret: () => 'probe-secret',
      getToken: async () => 'oidc-secret',
      fetchImpl: async () => new Response('private upstream detail', { status: upstreamStatus }),
    });

    const response = await handler(request());
    const body = await response.text();

    assert.equal(response.status, expectedStatus);
    assert.deepEqual(JSON.parse(body), { error: expectedError });
    assert.doesNotMatch(body, /private upstream detail|oidc-secret|probe-secret/);
  }
});

test('rejects malformed upstream data and network failures safely', async () => {
  for (const fetchImpl of [
    async () => Response.json({ data: [{ id: 'skill-without-name' }] }),
    async () => new Response('invalid json', { status: 200 }),
    async () => { throw new Error('private network detail'); },
  ]) {
    const handler = createSearchHandler({
      getAccessSecret: () => 'probe-secret',
      getToken: async () => 'oidc-secret',
      fetchImpl,
    });

    const response = await handler(request());
    const body = await response.text();

    assert.equal(response.status, 502);
    assert.match(body, /INVALID_UPSTREAM_RESPONSE|UPSTREAM_UNAVAILABLE/);
    assert.doesNotMatch(body, /private network detail|oidc-secret|probe-secret/);
  }
});
