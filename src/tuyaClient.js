import { TuyaContext } from '@tuya/tuya-connector-nodejs';

const DATA_CENTERS = {
  cn: 'https://openapi.tuyacn.com',
  us: 'https://openapi.tuyaus.com',
  eu: 'https://openapi.tuyaeu.com',
  in: 'https://openapi.tuyain.com',
  ea: 'https://openapi-ueaz.tuyaus.com',
  we: 'https://openapi-weaz.tuyaeu.com',
};

export class TuyaLinkError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'TuyaLinkError';
    this.details = details;
  }
}

export function requireTuyaConfig(env = process.env) {
  const accessKey = env.MONIK_TUYA_ACCESS_ID || env.TUYA_ACCESS_ID;
  const secretKey = env.MONIK_TUYA_ACCESS_SECRET || env.TUYA_ACCESS_SECRET;
  const dataCenter = env.TUYA_DATA_CENTER || 'eu';
  const baseUrl = env.TUYA_BASE_URL || DATA_CENTERS[dataCenter];
  const schema = env.TUYA_SCHEMA || 'tuyaSmart';
  const countryCode = env.TUYA_COUNTRY_CODE || '49';

  const missing = [];
  if (!accessKey) missing.push('MONIK_TUYA_ACCESS_ID');
  if (!secretKey) missing.push('MONIK_TUYA_ACCESS_SECRET');
  if (!baseUrl) missing.push('TUYA_BASE_URL or valid TUYA_DATA_CENTER');

  if (missing.length > 0) {
    throw new TuyaLinkError('MoniK Tuya connector is not configured on the server.', { missing });
  }

  return { accessKey, secretKey, baseUrl, schema, countryCode };
}

export function createTuyaContext(config = requireTuyaConfig()) {
  return new TuyaContext({
    baseUrl: config.baseUrl,
    accessKey: config.accessKey,
    secretKey: config.secretKey,
  });
}

function assertTuyaSuccess(response, action) {
  if (!response?.success) {
    throw new TuyaLinkError(`Tuya ${action} failed.`, {
      code: response?.code,
      message: response?.msg || response?.message,
      response,
    });
  }

  return response.result;
}

export async function loginTuyaAccount({ username, password, countryCode, schema }, options = {}) {
  if (!username || !password) {
    throw new TuyaLinkError('Username and password are required.');
  }

  const config = options.config || requireTuyaConfig();
  const context = options.context || createTuyaContext(config);
  const loginResult = await context.request({
    path: '/v1.0/iot-01/associated-users/actions/authorized-login',
    method: 'POST',
    body: {
      username,
      password,
      country_code: countryCode || config.countryCode,
      schema: schema || config.schema,
    },
  });

  return assertTuyaSuccess(loginResult, 'account login');
}

export async function getTuyaDevicesByUid(uid, options = {}) {
  if (!uid) {
    throw new TuyaLinkError('Tuya UID is required to fetch devices.');
  }

  const config = options.config || requireTuyaConfig();
  const context = options.context || createTuyaContext(config);
  const devicesResult = await context.request({
    path: `/v1.0/users/${encodeURIComponent(uid)}/devices`,
    method: 'GET',
  });

  return assertTuyaSuccess(devicesResult, 'device import');
}

export async function linkTuyaAccountAndImportDevices(credentials, options = {}) {
  const token = await loginTuyaAccount(credentials, options);
  const devices = await getTuyaDevicesByUid(token.uid, options);

  return {
    account: {
      uid: token.uid,
      expireTime: token.expire_time,
      accessToken: token.access_token,
      refreshToken: token.refresh_token,
    },
    devices,
  };
}

export function publicTuyaConfig(env = process.env) {
  return {
    dataCenter: env.TUYA_DATA_CENTER || 'eu',
    baseUrl: env.TUYA_BASE_URL || DATA_CENTERS[env.TUYA_DATA_CENTER || 'eu'],
    schema: env.TUYA_SCHEMA || 'tuyaSmart',
    countryCode: env.TUYA_COUNTRY_CODE || '49',
  };
}
