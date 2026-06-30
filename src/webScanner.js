import { networkInterfaces } from 'node:os';
import net from 'node:net';

const DEFAULT_SCAN_PORT = Number(process.env.MONIK_LOCAL_SCAN_PORT || 6668);
const DEFAULT_SCAN_TIMEOUT_MS = Number(process.env.MONIK_LOCAL_SCAN_TIMEOUT_MS || 350);
const DEFAULT_SCAN_CIDR = process.env.MONIK_LOCAL_SCAN_CIDR || '';

export class WebScannerError extends Error {
  constructor(message, statusCode = 400, details = {}) {
    super(message);
    this.name = 'WebScannerError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

function compact(value) {
  if (value === undefined || value === null || value === '') return null;
  return value;
}

function asArray(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.devices)) return payload.devices;
  if (Array.isArray(payload?.payload?.devices)) return payload.payload.devices;
  if (Array.isArray(payload?.result?.devices)) return payload.result.devices;
  if (Array.isArray(payload?.data?.devices)) return payload.data.devices;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
}

function normalizeDevice(device = {}, source = 'unknown') {
  const rawId = compact(device.id) || compact(device.devId) || compact(device.deviceId) || compact(device.iotId) || compact(device.skill_id);
  const name = compact(device.name) || compact(device.deviceName) || compact(device.productName) || compact(device.title) || rawId || 'Unknown device';
  const localKey = compact(device.localKey) || compact(device.local_key) || compact(device.key) || compact(device.controlKey);
  const localIp = compact(device.localIp) || compact(device.local_ip) || compact(device.ip) || compact(device.host);
  const productId = compact(device.productId) || compact(device.product_id);
  const category = compact(device.category) || compact(device.categoryCode) || compact(device.type);

  return {
    id: rawId || `${source}:${name}`,
    name,
    localKey,
    localIp,
    productId,
    category,
    online: Boolean(device.online ?? device.isOnline ?? device.reachable ?? false),
    source,
    raw: device,
  };
}

function normalizeSnapshot(payload, source) {
  return asArray(payload).map((device) => normalizeDevice(device, source));
}

function deviceKeys(device) {
  return [device.id, device.name, device.productId].filter(Boolean).map((value) => String(value).toLowerCase());
}

function sameDevice(left, right) {
  const rightKeys = new Set(deviceKeys(right));
  return deviceKeys(left).some((key) => rightKeys.has(key));
}

function parseHeaderLines(lines = '') {
  return Object.fromEntries(
    String(lines)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const index = line.indexOf(':');
        if (index === -1) return [line, ''];
        return [line.slice(0, index).trim(), line.slice(index + 1).trim()];
      }),
  );
}

async function fetchJsonSnapshot({ url, label, token, headers = {} }) {
  if (!url) {
    return {
      configured: false,
      label,
      devices: [],
      error: `${label} URL is not configured.`,
    };
  }

  const requestHeaders = { accept: 'application/json', ...headers };
  if (token) requestHeaders.authorization = `Bearer ${token}`;

  const response = await fetch(url, { method: 'GET', headers: requestHeaders });
  const text = await response.text();
  let payload;

  try {
    payload = text ? JSON.parse(text) : {};
  } catch (error) {
    throw new WebScannerError(`${label} returned non-JSON response.`, 502, { url, status: response.status, error: error.message });
  }

  if (!response.ok) {
    throw new WebScannerError(`${label} read failed.`, 502, { url, status: response.status, payload });
  }

  return {
    configured: true,
    label,
    devices: normalizeSnapshot(payload, label),
    payload,
  };
}

function getLocalPrefixes() {
  if (DEFAULT_SCAN_CIDR) {
    return DEFAULT_SCAN_CIDR.split(',').map((prefix) => prefix.trim()).filter(Boolean);
  }

  const prefixes = new Set();
  for (const entries of Object.values(networkInterfaces())) {
    for (const entry of entries || []) {
      if (entry.family !== 'IPv4' || entry.internal) continue;
      const parts = entry.address.split('.');
      if (parts.length === 4) prefixes.add(parts.slice(0, 3).join('.'));
    }
  }

  return [...prefixes];
}

function hostsFromPrefixes(prefixes, limit) {
  const hosts = [];
  for (const prefix of prefixes) {
    const normalized = prefix.replace(/\.0\/24$/, '').replace(/\.$/, '');
    for (let index = 1; index < 255; index += 1) {
      hosts.push(`${normalized}.${index}`);
      if (hosts.length >= limit) return hosts;
    }
  }
  return hosts;
}

function probePort(host, port, timeoutMs) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let settled = false;

    function done(open) {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve({ ip: host, port, open });
    }

    socket.setTimeout(timeoutMs);
    socket.once('connect', () => done(true));
    socket.once('timeout', () => done(false));
    socket.once('error', () => done(false));
    socket.connect(port, host);
  });
}

async function scanPort({ port = DEFAULT_SCAN_PORT, timeoutMs = DEFAULT_SCAN_TIMEOUT_MS, limit = 254, concurrency = 64 } = {}) {
  const prefixes = getLocalPrefixes();
  const hosts = hostsFromPrefixes(prefixes, limit);
  const open = [];
  let cursor = 0;

  async function worker() {
    while (cursor < hosts.length) {
      const host = hosts[cursor];
      cursor += 1;
      const result = await probePort(host, port, timeoutMs);
      if (result.open) open.push(result);
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, hosts.length || 1) }, worker));

  return { port, prefixes, scannedHosts: hosts.length, open };
}

function buildLocalControlList({ stratoDevices, yandexDevices, openHosts, port }) {
  const openIps = new Set(openHosts.map((host) => host.ip));

  return stratoDevices.map((device) => {
    const matchedYandex = yandexDevices.find((candidate) => sameDevice(device, candidate)) || null;
    const localIp = device.localIp || matchedYandex?.localIp || null;
    const portOpen = localIp ? openIps.has(localIp) : false;

    return {
      id: device.id,
      name: device.name,
      localIp,
      localKey: device.localKey || null,
      online: device.online || matchedYandex?.online || portOpen,
      yandexRefreshed: Boolean(matchedYandex),
      missingInYandexRefresh: !matchedYandex,
      port6668Open: portOpen,
      control: device.localKey
        ? {
            on: { protocol: 'tuya-local', ip: localIp, port, localKey: device.localKey, command: 'switch_on' },
            off: { protocol: 'tuya-local', ip: localIp, port, localKey: device.localKey, command: 'switch_off' },
          }
        : null,
      source: 'strato-readonly',
    };
  }).filter((device) => device.localIp || device.localKey || device.port6668Open);
}

export async function runReadOnlyWebScan(options = {}) {
  const yandexUrl = options.yandexUrl ?? process.env.MONIK_YANDEX_DEVICES_URL;
  const yandexToken = options.yandexToken ?? process.env.MONIK_YANDEX_ACCESS_TOKEN;
  const stratoUrl = options.stratoUrl ?? process.env.MONIK_STRATO_DEVICES_URL;
  const stratoToken = options.stratoToken ?? process.env.MONIK_STRATO_ACCESS_TOKEN;
  const stratoHeaders = {
    ...parseHeaderLines(process.env.MONIK_STRATO_EXTRA_HEADERS),
  };

  if (process.env.MONIK_TUYA_ACCESS_ID) {
    stratoHeaders['x-monik-tuya-access-id'] = process.env.MONIK_TUYA_ACCESS_ID;
  }
  if (process.env.MONIK_TUYA_ACCESS_SECRET) {
    stratoHeaders['x-monik-tuya-access-secret'] = process.env.MONIK_TUYA_ACCESS_SECRET;
  }

  const [yandexSnapshot, stratoSnapshot, localScan] = await Promise.all([
    fetchJsonSnapshot({ url: yandexUrl, token: yandexToken, label: 'yandex' }),
    fetchJsonSnapshot({ url: stratoUrl, token: stratoToken, headers: stratoHeaders, label: 'strato' }),
    scanPort(options.scan),
  ]);

  const localDevices = buildLocalControlList({
    stratoDevices: stratoSnapshot.devices,
    yandexDevices: yandexSnapshot.devices,
    openHosts: localScan.open,
    port: localScan.port,
  });

  return {
    readOnly: true,
    writesPerformed: false,
    generatedAt: new Date().toISOString(),
    yandex: {
      configured: yandexSnapshot.configured,
      deviceCount: yandexSnapshot.devices.length,
      error: yandexSnapshot.error || null,
    },
    strato: {
      configured: stratoSnapshot.configured,
      deviceCount: stratoSnapshot.devices.length,
      error: stratoSnapshot.error || null,
    },
    localScan,
    localDevices,
    notes: [
      'No write to Strato server.',
      'No write to phone.',
      'No Android project file changes.',
      'If Yandex refresh has fewer devices, Strato snapshot remains the source shown here.',
    ],
  };
}
