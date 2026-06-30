import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { AdbBridgeError, clearAdbLogcat, getAdbStatus, readAdbLogcat, readMonikTuyaExport } from './adbBridge.js';
import { MonikTokenError, requestMonikToken } from './monikTokenClient.js';
import {
  OAuthError,
  createAuthorizationCode,
  exchangeAuthorizationCode,
  getAccountFromAuthorizationHeader,
  publicOAuthConfig,
  refreshAccessToken,
} from './oauthStore.js';
import { DeviceImportError, getImportedDevices, importDevicesFromSdk } from './deviceStore.js';
import { WebScannerError, runReadOnlyWebScan } from './webScanner.js';

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


async function readBodyText(request) {
  const chunks = [];

  for await (const chunk of request) {
    chunks.push(chunk);
  }

  return Buffer.concat(chunks).toString('utf8');
}

async function readFormOrJsonBody(request) {
  const bodyText = await readBodyText(request);
  const contentType = request.headers['content-type'] || '';

  if (contentType.includes('application/json')) {
    return bodyText ? JSON.parse(bodyText) : {};
  }

  return Object.fromEntries(new URLSearchParams(bodyText));
}

function sendHtml(response, statusCode, html, headers = {}) {
  response.writeHead(statusCode, { 'content-type': 'text/html; charset=utf-8', ...headers });
  response.end(html);
}

function sendRedirect(response, location) {
  response.writeHead(302, { location });
  response.end();
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


function handleOAuthAuthorizePage(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);
  const params = Object.fromEntries(url.searchParams);
  const html = `<!doctype html>
<html lang="bg">
  <head><meta charset="utf-8"><title>MoniK Account Link</title></head>
  <body style="font-family: system-ui; max-width: 720px; margin: 40px auto;">
    <h1>MoniK account linking</h1>
    <p>Линкване като Алиса/Yandex/Alexa: user потвърждава акаунта, после връщаме authorization code към redirect_uri.</p>
    <form method="post" action="/oauth/authorize">
      <input type="hidden" name="client_id" value="${params.client_id || ''}">
      <input type="hidden" name="redirect_uri" value="${params.redirect_uri || ''}">
      <input type="hidden" name="response_type" value="${params.response_type || 'code'}">
      <input type="hidden" name="scope" value="${params.scope || ''}">
      <input type="hidden" name="state" value="${params.state || ''}">
      <label>Email / акаунт<br><input name="account" required style="width: 100%; padding: 10px;"></label><br><br>
      <label>Парола<br><input name="password" type="password" required style="width: 100%; padding: 10px;"></label><br><br>
      <button type="submit" style="padding: 12px 18px;">Link MoniK account</button>
    </form>
  </body>
</html>`;

  sendHtml(response, 200, html);
}

async function handleOAuthAuthorizeSubmit(request, response) {
  try {
    const body = await readFormOrJsonBody(request);
    if (body.response_type && body.response_type !== 'code') {
      throw new OAuthError('Only response_type=code is supported.');
    }

    const { code, state } = createAuthorizationCode({
      account: body.account,
      clientId: body.client_id,
      redirectUri: body.redirect_uri,
      scope: body.scope,
      state: body.state,
    });
    const redirectUrl = new URL(body.redirect_uri);
    redirectUrl.searchParams.set('code', code);
    if (state) redirectUrl.searchParams.set('state', state);

    sendRedirect(response, redirectUrl.toString());
  } catch (error) {
    const statusCode = error instanceof OAuthError ? error.statusCode : 500;
    sendJson(response, statusCode, { error: error.message, details: error.details });
  }
}

async function handleOAuthToken(request, response) {
  try {
    const body = await readFormOrJsonBody(request);
    const grantType = body.grant_type;
    let result;

    if (grantType === 'authorization_code') {
      result = exchangeAuthorizationCode({
        clientId: body.client_id,
        clientSecret: body.client_secret,
        code: body.code,
        redirectUri: body.redirect_uri,
      });
    } else if (grantType === 'refresh_token') {
      result = refreshAccessToken({
        clientId: body.client_id,
        clientSecret: body.client_secret,
        refreshToken: body.refresh_token,
      });
    } else {
      throw new OAuthError('Unsupported grant_type.');
    }

    sendJson(response, 200, result);
  } catch (error) {
    const statusCode = error instanceof OAuthError ? error.statusCode : 500;
    sendJson(response, statusCode, { error: error.message, details: error.details });
  }
}

function handleOAuthAccount(request, response) {
  try {
    sendJson(response, 200, getAccountFromAuthorizationHeader(request.headers.authorization || ''));
  } catch (error) {
    const statusCode = error instanceof OAuthError ? error.statusCode : 500;
    sendJson(response, statusCode, { error: error.message, details: error.details });
  }
}


async function handleWebScan(request, response) {
  try {
    const options = request.method === 'POST' ? await readJsonBody(request) : {};
    sendJson(response, 200, await runReadOnlyWebScan(options));
  } catch (error) {
    const statusCode = error instanceof WebScannerError ? error.statusCode : 500;
    sendJson(response, statusCode, {
      readOnly: true,
      writesPerformed: false,
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


  if (request.method === 'GET' && url.pathname === '/.well-known/oauth-authorization-server') {
    sendJson(response, 200, publicOAuthConfig(`http://${request.headers.host}`));
    return;
  }

  if (request.method === 'GET' && url.pathname === '/oauth/authorize') {
    handleOAuthAuthorizePage(request, response);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/oauth/authorize') {
    await handleOAuthAuthorizeSubmit(request, response);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/oauth/token') {
    await handleOAuthToken(request, response);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/monik/account') {
    handleOAuthAccount(request, response);
    return;
  }

  if ((request.method === 'GET' || request.method === 'POST') && url.pathname === '/api/monik/web-scan') {
    await handleWebScan(request, response);
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
