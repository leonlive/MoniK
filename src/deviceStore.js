let devices = [];
let lastImport = null;

export class DeviceImportError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'DeviceImportError';
    this.details = details;
  }
}

function normalizeDevice(device) {
  if (!device || typeof device !== 'object') {
    throw new DeviceImportError('Every device must be an object.');
  }

  const id = device.id || device.devId || device.deviceId;
  const name = device.name || device.deviceName || device.productName;

  if (!id) {
    throw new DeviceImportError('Device is missing id/devId/deviceId.', { device });
  }

  return {
    id: String(id),
    name: name ? String(name) : String(id),
    productId: device.productId || device.product_id || null,
    category: device.category || device.categoryCode || null,
    online: Boolean(device.online ?? device.isOnline ?? false),
    raw: device,
  };
}

export function importDevicesFromSdk(payload) {
  const incomingDevices = Array.isArray(payload) ? payload : payload?.devices;

  if (!Array.isArray(incomingDevices)) {
    throw new DeviceImportError('Expected a devices array from the Tuya SDK client.');
  }

  devices = incomingDevices.map(normalizeDevice);
  lastImport = new Date().toISOString();

  return {
    importedDevices: devices.length,
    lastImport,
    devices,
  };
}

export function getImportedDevices() {
  return {
    importedDevices: devices.length,
    lastImport,
    devices,
  };
}
