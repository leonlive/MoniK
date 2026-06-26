import { spawn } from 'node:child_process';

const port = String(Number(process.env.PORT || 4173));
const baseUrl = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ['src/server.js'], {
  env: { ...process.env, PORT: port },
  stdio: ['ignore', 'pipe', 'pipe'],
});

async function waitForServer() {
  const deadline = Date.now() + 5000;
  let lastError;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }

    await new Promise((resolve) => setTimeout(resolve, 150));
  }

  throw lastError || new Error('Server did not become ready.');
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

try {
  await waitForServer();

  const page = await fetch(baseUrl);
  const html = await page.text();
  assert(page.status === 200, `Expected page status 200, got ${page.status}`);
  assert(html.includes('id="tuyaLinkForm"'), 'Expected Tuya link form on the test page.');
  assert(html.includes('Логин и импорт на устройства'), 'Expected real login/import submit button.');
  assert(html.includes('value="49"'), 'Expected international country code 49 option.');
  assert(html.includes('value="359"'), 'Expected Bulgaria country code 359 option.');

  const config = await fetch(`${baseUrl}/api/tuya/config`);
  assert(config.status === 200, `Expected config status 200, got ${config.status}`);
  const configPayload = await config.json();
  assert(configPayload.countryCode === '49', `Expected default country code 49, got ${configPayload.countryCode}`);

  const link = await fetch(`${baseUrl}/api/tuya/link`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: 'missing-config-check', password: 'missing-config-check' }),
  });
  const payload = await link.json();
  assert(link.status === 400, `Expected missing-config status 400, got ${link.status}`);
  assert(payload.linked === false, 'Expected linked=false when Tuya credentials are not configured.');

  console.log(`OK: test page works at ${baseUrl}`);
} finally {
  server.kill();
}
