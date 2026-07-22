export class TuyaLinkError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'TuyaLinkError';
    this.details = details;
  }
}

const REMOVED_FLOW_MESSAGE =
  'Tuya Cloud developer connector flow was removed. Use POST /api/monik/devices/import with devices collected by the mobile SDK client.';

export function requireTuyaConfig() {
  throw new TuyaLinkError(REMOVED_FLOW_MESSAGE, {
    replacementEndpoint: '/api/monik/devices/import',
  });
}

export function createTuyaContext() {
  throw new TuyaLinkError(REMOVED_FLOW_MESSAGE, {
    replacementEndpoint: '/api/monik/devices/import',
  });
}

export async function loginTuyaAccount() {
  throw new TuyaLinkError(REMOVED_FLOW_MESSAGE, {
    replacementEndpoint: '/api/monik/devices/import',
  });
}

export async function getTuyaDevicesByUid() {
  throw new TuyaLinkError(REMOVED_FLOW_MESSAGE, {
    replacementEndpoint: '/api/monik/devices/import',
  });
}

export async function linkTuyaAccountAndImportDevices() {
  throw new TuyaLinkError(REMOVED_FLOW_MESSAGE, {
    replacementEndpoint: '/api/monik/devices/import',
  });
}

export function publicTuyaConfig() {
  return {
    removed: true,
    message: REMOVED_FLOW_MESSAGE,
    replacementEndpoint: '/api/monik/devices/import',
  };
}
