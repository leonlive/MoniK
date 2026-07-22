import { randomUUID } from 'node:crypto';

const DEFAULT_CLIENT_ID = process.env.MONIK_OAUTH_CLIENT_ID || 'alice-dev-client';
const DEFAULT_CLIENT_SECRET = process.env.MONIK_OAUTH_CLIENT_SECRET || 'alice-dev-secret';
const DEFAULT_REDIRECT_URI = process.env.MONIK_OAUTH_REDIRECT_URI || 'http://localhost:4173/oauth/callback/dev';

const authCodes = new Map();
const accessTokens = new Map();
const refreshTokens = new Map();

export class OAuthError extends Error {
  constructor(message, statusCode = 400, details = {}) {
    super(message);
    this.name = 'OAuthError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

export function publicOAuthConfig(origin = 'http://localhost:4173') {
  return {
    authorization_endpoint: `${origin}/oauth/authorize`,
    token_endpoint: `${origin}/oauth/token`,
    response_types_supported: ['code'],
    grant_types_supported: ['authorization_code', 'refresh_token'],
    token_endpoint_auth_methods_supported: ['client_secret_post'],
    dev_client_id: DEFAULT_CLIENT_ID,
    dev_redirect_uri: DEFAULT_REDIRECT_URI,
  };
}

function assertClient({ clientId, clientSecret, redirectUri, requireSecret = false }) {
  if (clientId !== DEFAULT_CLIENT_ID) {
    throw new OAuthError('Unknown OAuth client_id.', 401, { clientId });
  }

  if (requireSecret && clientSecret !== DEFAULT_CLIENT_SECRET) {
    throw new OAuthError('Invalid OAuth client_secret.', 401);
  }

  if (redirectUri && DEFAULT_REDIRECT_URI !== '*' && redirectUri !== DEFAULT_REDIRECT_URI) {
    throw new OAuthError('Invalid OAuth redirect_uri.', 400, { redirectUri, expected: DEFAULT_REDIRECT_URI });
  }
}

export function createAuthorizationCode({ clientId, redirectUri, scope = '', state = '', account = '' }) {
  assertClient({ clientId, redirectUri });

  if (!account) {
    throw new OAuthError('Account/email is required for account linking.');
  }

  const code = randomUUID();
  authCodes.set(code, {
    account,
    clientId,
    createdAt: Date.now(),
    redirectUri,
    scope,
    state,
  });

  return { code, state };
}

export function exchangeAuthorizationCode({ code, clientId, clientSecret, redirectUri }) {
  assertClient({ clientId, clientSecret, redirectUri, requireSecret: true });

  const record = authCodes.get(code);
  if (!record) {
    throw new OAuthError('Invalid or already used authorization code.', 400);
  }

  if (record.clientId !== clientId || record.redirectUri !== redirectUri) {
    throw new OAuthError('Authorization code does not match this client or redirect URI.', 400);
  }

  authCodes.delete(code);

  const accessToken = `monik_at_${randomUUID()}`;
  const refreshToken = `monik_rt_${randomUUID()}`;
  const tokenRecord = {
    account: record.account,
    clientId,
    issuedAt: Date.now(),
    scope: record.scope,
  };

  accessTokens.set(accessToken, tokenRecord);
  refreshTokens.set(refreshToken, tokenRecord);

  return {
    access_token: accessToken,
    expires_in: 3600,
    refresh_token: refreshToken,
    token_type: 'Bearer',
  };
}

export function refreshAccessToken({ refreshToken, clientId, clientSecret }) {
  assertClient({ clientId, clientSecret, requireSecret: true });

  const record = refreshTokens.get(refreshToken);
  if (!record) {
    throw new OAuthError('Invalid refresh token.', 400);
  }

  const accessToken = `monik_at_${randomUUID()}`;
  accessTokens.set(accessToken, { ...record, issuedAt: Date.now() });

  return {
    access_token: accessToken,
    expires_in: 3600,
    token_type: 'Bearer',
  };
}

export function getAccountFromAuthorizationHeader(header = '') {
  const match = header.match(/^Bearer\s+(.+)$/i);
  if (!match) {
    throw new OAuthError('Missing bearer token.', 401);
  }

  const record = accessTokens.get(match[1]);
  if (!record) {
    throw new OAuthError('Invalid bearer token.', 401);
  }

  return {
    account: record.account,
    clientId: record.clientId,
    scope: record.scope,
  };
}
