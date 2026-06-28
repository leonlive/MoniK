import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { sign } from 'node:crypto';

export class MonikTokenError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'MonikTokenError';
    this.details = details;
  }
}

function requireTokenConfig(env = process.env) {
  const accessId = env.MONIK_TUYA_ACCESS_ID;
  const privateKeyPath = env.MONIK_TUYA_PRIVATE_KEY_PATH;
  const publicKeyPath = env.MONIK_TUYA_PUBLIC_KEY_PATH;
  const tokenUrl = env.MONIK_SERVER_TOKEN_URL;

  const missing = [];
  if (!accessId) missing.push('MONIK_TUYA_ACCESS_ID');
  if (!privateKeyPath) missing.push('MONIK_TUYA_PRIVATE_KEY_PATH');
  if (!publicKeyPath) missing.push('MONIK_TUYA_PUBLIC_KEY_PATH');

  if (missing.length > 0) {
    throw new MonikTokenError('Missing MoniK token key file configuration.', { missing });
  }

  return { accessId, privateKeyPath, publicKeyPath, tokenUrl };
}

function canonicalJson(value) {
  return JSON.stringify(value, Object.keys(value).sort());
}

export async function createSignedTokenRequest(payload = {}, options = {}) {
  const config = options.config || requireTokenConfig(options.env);
  const [privateKey, publicKey] = await Promise.all([
    readFile(config.privateKeyPath, 'utf8'),
    readFile(config.publicKeyPath, 'utf8'),
  ]);

  const requestBody = {
    accessId: config.accessId,
    nonce: randomUUID(),
    payload,
    timestamp: new Date().toISOString(),
  };
  const bodyToSign = canonicalJson(requestBody);
  const signature = sign('sha256', Buffer.from(bodyToSign), privateKey).toString('base64');

  return {
    tokenUrl: config.tokenUrl || null,
    body: requestBody,
    headers: {
      'content-type': 'application/json',
      'x-monik-access-id': config.accessId,
      'x-monik-public-key': Buffer.from(publicKey).toString('base64'),
      'x-monik-signature': signature,
    },
  };
}

export async function requestMonikToken(payload = {}, options = {}) {
  const signedRequest = await createSignedTokenRequest(payload, options);

  if (!signedRequest.tokenUrl) {
    return {
      sent: false,
      reason: 'MONIK_SERVER_TOKEN_URL is not configured. Returning signed request only.',
      signedRequest,
    };
  }

  const response = await fetch(signedRequest.tokenUrl, {
    method: 'POST',
    headers: signedRequest.headers,
    body: JSON.stringify(signedRequest.body),
  });
  const contentType = response.headers.get('content-type') || '';
  const responseBody = contentType.includes('application/json') ? await response.json() : await response.text();

  return {
    sent: true,
    ok: response.ok,
    status: response.status,
    response: responseBody,
  };
}
