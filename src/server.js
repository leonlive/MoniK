import { createServer } from 'node:http';
import { networkInterfaces } from 'node:os';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DeviceImportError, getImportedDevices, importDevicesFromSdk } from './deviceStore.js';

const PORT = Number(process.env.PORT || 4173);
const PUBLIC_DIR = fileURLToPath(new URL('../public/', import.meta.url));
const PAIRING_CODE = String(Math.floor(100000 + Math.random() * 900000));

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};


function getLanUrls(request) {
  const hostHeader = request.headers.host || `localhost:${PORT}`;
  const port = hostHeader.split(':')[1] || String(PORT);
  const urls = [`http://localhost:${port}`];

  for (const addresses of Object.values(networkInterfaces())) {
    for (const address of addresses || []) {
      if (address.family === 'IPv4' && !address.internal) {
        urls.push(`http://${address.address}:${port}`);
      }
    }
  }

  return [...new Set(urls)];
}

function getPairingInfo(request) {
  const baseUrls = getLanUrls(request);

  return {
    pairingCode: PAIRING_CODE,
    baseUrls,
    importEndpoints: baseUrls.map((baseUrl) => `${baseUrl}/api/monik/devices/import`),
    devicesEndpoints: baseUrls.map((baseUrl) => `${baseUrl}/api/monik/devices`),
    instructions: 'Phone must be on the same Wi-Fi/LAN. Send devices to the import endpoint with x-monik-pairing-code header or pairingCode in JSON body.',
  };
}

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
    const receivedCode = request.headers['x-monik-pairing-code'] || payload.pairingCode;

    if (receivedCode !== PAIRING_CODE) {
      sendJson(response, 401, {
        imported: false,
        error: 'Invalid or missing MoniK pairing code.',
      });
      return;
    }

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

async function route(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);

  if (request.method === 'GET' && url.pathname === '/health') {
    sendJson(response, 200, { ok: true, mode: 'tuya-mobile-sdk-bridge', pairingCode: PAIRING_CODE });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/monik/pairing') {
    sendJson(response, 200, getPairingInfo(request));
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
