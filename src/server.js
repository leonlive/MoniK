import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { AdbBridgeError, clearAdbLogcat, getAdbStatus, readAdbLogcat, readMonikTuyaExport } from './adbBridge.js';
import { MonikTokenError, requestMonikToken } from './monikTokenClient.js';
import { DeviceImportError, getImportedDevices, importDevicesFromSdk } from './deviceStore.js';

const PORT = Number(process.env.PORT || 4173);
const PUBLIC_DIR = fileURLToPath(new URL('../public/', import.meta.url));

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};


function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, { 'content-type': MIME_TYPES['.json'] });
  response.end(JSON.stringify(payload));
}

async function readJsonBody(request) {
  const chunks = [];

  for await (const chunk of request) {
    chunks.push(chunk);
  }

  if (chunks.length === 0) return {};

  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

async function serveStatic(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);
  const requestedPath = url.pathname === '/' ? '/index.html' : url.pathname;
  const safePath = normalize(requestedPath).replace(/^([.][.][/\\])+/, '');
  const filePath = join(PUBLIC_DIR, safePath);

  if (!filePath.startsWith(PUBLIC_DIR)) {
    sendJson(response, 403, { error: 'Forbidden' });
    return;
  }

  try {
    const content = await readFile(filePath);
    response.writeHead(200, { 'content-type': MIME_TYPES[extname(filePath)] || 'application/octet-stream' });
    response.end(content);
  } catch {
    sendJson(response, 404, { error: 'Not found' });
  }
}

async function handleDeviceImport(request, response) {
  try {
    const payload = await readJsonBody(request);
    const result = importDevicesFromSdk(payload);

    sendJson(response, 200, {
      imported: true,
      ...result,
    });
  } catch (error) {
    const statusCode = error instanceof DeviceImportError ? 400 : 500;
    sendJson(response, statusCode, {
      imported: false,
      error: error.message,
      details: error.details,
    });
  }
}




async function handleLogcatRead(request, response) {
  try {
    const url = new URL(request.url, `http://${request.headers.host}`);
    const result = await readAdbLogcat({
      filter: url.searchParams.get('filter') || '',
      lines: url.searchParams.get('lines') || 600,
    });
    sendJson(response, 200, result);
  } catch (error) {
    const statusCode = error instanceof AdbBridgeError ? 400 : 500;
    sendJson(response, statusCode, {
      logcat: false,
      error: error.message,
      details: error.details,
    });
  }
}

async function handleLogcatClear(response) {
  try {
    sendJson(response, 200, await clearAdbLogcat());
  } catch (error) {
    const statusCode = error instanceof AdbBridgeError ? 400 : 500;
    sendJson(response, statusCode, {
      cleared: false,
      error: error.message,
      details: error.details,
    });
  }
}

async function handleTokenRequest(request, response) {
  try {
    const payload = await readJsonBody(request);
    const result = await requestMonikToken(payload);
    sendJson(response, result.sent && result.ok === false ? 502 : 200, result);
  } catch (error) {
    const statusCode = error instanceof MonikTokenError ? 400 : 500;
    sendJson(response, statusCode, {
      tokenRequested: false,
      error: error.message,
      details: error.details,
    });
  }
}

async function handleAdbImport(request, response) {
  try {
    const options = await readJsonBody(request);
    const payload = await readMonikTuyaExport(options);
    const result = importDevicesFromSdk(payload);

    sendJson(response, 200, {
      imported: true,
      source: 'adb',
      ...result,
    });
  } catch (error) {
    const statusCode = error instanceof AdbBridgeError || error instanceof DeviceImportError ? 400 : 500;
    sendJson(response, statusCode, {
      imported: false,
      source: 'adb',
      error: error.message,
      details: error.details,
    });
  }
}

async function route(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);

  if (request.method === 'GET' && url.pathname === '/health') {
    sendJson(response, 200, { ok: true, mode: 'monik-adb-sdk-bridge' });
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/monik/token/request') {
    await handleTokenRequest(request, response);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/monik/adb/logcat/clear') {
    await handleLogcatClear(response);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/monik/adb/logcat') {
    await handleLogcatRead(request, response);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/monik/adb/status') {
    sendJson(response, 200, await getAdbStatus());
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/monik/adb/import') {
    await handleAdbImport(request, response);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/monik/devices') {
    sendJson(response, 200, getImportedDevices());
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/monik/devices/import') {
    await handleDeviceImport(request, response);
    return;
  }

  if (request.method === 'GET' || request.method === 'HEAD') {
    await serveStatic(request, response);
    return;
  }

  sendJson(response, 405, { error: 'Method not allowed' });
}

createServer((request, response) => {
  route(request, response).catch((error) => {
    sendJson(response, 500, { error: error.message });
  });
}).listen(PORT, () => {
  console.log(`MoniK Tuya SDK bridge listening on http://localhost:${PORT}`);
});
