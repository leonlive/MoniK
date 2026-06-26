import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { linkTuyaAccountAndImportDevices, publicTuyaConfig, TuyaLinkError } from './tuyaClient.js';

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

async function handleLinkTuya(request, response) {
  try {
    const credentials = await readJsonBody(request);
    const result = await linkTuyaAccountAndImportDevices(credentials);

    sendJson(response, 200, {
      linked: true,
      uid: result.account.uid,
      tokenExpiresIn: result.account.expireTime,
      importedDevices: Array.isArray(result.devices) ? result.devices.length : 0,
      devices: result.devices,
    });
  } catch (error) {
    const statusCode = error instanceof TuyaLinkError ? 400 : 500;
    sendJson(response, statusCode, {
      linked: false,
      error: error.message,
      details: error.details,
    });
  }
}

async function route(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);

  if (request.method === 'GET' && url.pathname === '/health') {
    sendJson(response, 200, { ok: true });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/tuya/config') {
    sendJson(response, 200, publicTuyaConfig());
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/tuya/link') {
    await handleLinkTuya(request, response);
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
  console.log(`MoniK Tuya link server listening on http://localhost:${PORT}`);
});
