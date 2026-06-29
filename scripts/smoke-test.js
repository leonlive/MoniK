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
  assert(html.includes('id="adbImportForm"'), 'Expected ADB import form on the test page.');
  assert(html.includes('Вътре в MoniK app'), 'Expected integrated MoniK app wording.');
  assert(html.includes('Tuya SDK login'), 'Expected explanation that login is in the MoniK app.');
  assert(html.includes('Взимане от телефона с ADB'), 'Expected ADB phone bridge section.');

  const wellKnownResponse = await fetch(`${baseUrl}/.well-known/oauth-authorization-server`);
  const wellKnownPayload = await wellKnownResponse.json();
  assert(wellKnownResponse.status === 200, `Expected OAuth metadata 200, got ${wellKnownResponse.status}`);
  assert(wellKnownPayload.authorization_endpoint, 'Expected OAuth authorization endpoint.');

  const devRedirectUri = 'http://localhost:4173/oauth/callback/dev';
  const authorizePage = await fetch(`${baseUrl}/oauth/authorize?response_type=code&client_id=alice-dev-client&redirect_uri=${encodeURIComponent(devRedirectUri)}&state=smoke`);
  const authorizeHtml = await authorizePage.text();
  assert(authorizePage.status === 200, `Expected authorize page 200, got ${authorizePage.status}`);
  assert(authorizeHtml.includes('MoniK account linking'), 'Expected OAuth link page.');

  const authorizeSubmit = await fetch(`${baseUrl}/oauth/authorize`, {
    method: 'POST',
    redirect: 'manual',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      account: 'user@example.com',
      client_id: 'alice-dev-client',
      password: 'secret',
      redirect_uri: devRedirectUri,
      response_type: 'code',
      state: 'smoke',
    }),
  });
  assert(authorizeSubmit.status === 302, `Expected authorize redirect 302, got ${authorizeSubmit.status}`);
  const redirectLocation = authorizeSubmit.headers.get('location');
  const code = new URL(redirectLocation).searchParams.get('code');
  assert(code, 'Expected authorization code.');

  const tokenResponse = await fetch(`${baseUrl}/oauth/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: 'alice-dev-client',
      client_secret: 'alice-dev-secret',
      code,
      grant_type: 'authorization_code',
      redirect_uri: devRedirectUri,
    }),
  });
  const tokenPayload = await tokenResponse.json();
  assert(tokenResponse.status === 200, `Expected token response 200, got ${tokenResponse.status}`);
  assert(tokenPayload.access_token, 'Expected access token.');

  const accountResponse = await fetch(`${baseUrl}/api/monik/account`, {
    headers: { authorization: `Bearer ${tokenPayload.access_token}` },
  });
  const accountPayload = await accountResponse.json();
  assert(accountResponse.status === 200, `Expected account response 200, got ${accountResponse.status}`);
  assert(accountPayload.account === 'user@example.com', `Expected linked account, got ${accountPayload.account}`);

  const tokenMissingConfigResponse = await fetch(`${baseUrl}/api/monik/token/request`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ account: 'user@example.com' }),
  });
  assert(tokenMissingConfigResponse.status === 400, `Expected token missing config status 400, got ${tokenMissingConfigResponse.status}`);

  const logcatResponse = await fetch(`${baseUrl}/api/monik/adb/logcat?lines=50&filter=tuya`);
  assert([200, 400].includes(logcatResponse.status), `Expected logcat status 200 or 400, got ${logcatResponse.status}`);

  const adbStatusResponse = await fetch(`${baseUrl}/api/monik/adb/status`);
  const adbStatusPayload = await adbStatusResponse.json();
  assert(adbStatusResponse.status === 200, `Expected ADB status 200, got ${adbStatusResponse.status}`);
  assert('adbAvailable' in adbStatusPayload, 'Expected adbAvailable field.');

  const importResponse = await fetch(`${baseUrl}/api/monik/devices/import`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ devices: [{ devId: 'real-device-id', name: 'Lamp', online: true }] }),
  });
  const importPayload = await importResponse.json();
  assert(importResponse.status === 200, `Expected import status 200, got ${importResponse.status}`);
  assert(importPayload.imported === true, 'Expected imported=true.');
  assert(importPayload.importedDevices === 1, `Expected one imported device, got ${importPayload.importedDevices}`);

  const devices = await fetch(`${baseUrl}/api/monik/devices`);
  const devicesPayload = await devices.json();
  assert(devicesPayload.importedDevices === 1, 'Expected stored imported device.');

  console.log(`OK: SDK bridge works at ${baseUrl}`);
} finally {
  server.kill();
}
