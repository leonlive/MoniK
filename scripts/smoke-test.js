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
  assert(html.includes('id="deviceImportForm"'), 'Expected SDK device import form on the test page.');
  assert(html.includes('Без Tuya developer cloud keys'), 'Expected no-developer-cloud-key wording.');

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
