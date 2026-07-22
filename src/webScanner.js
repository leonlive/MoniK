import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { networkInterfaces, platform } from 'node:os';
import net from 'node:net';

const execFileAsync = promisify(execFile);

const DEFAULT_SCAN_PORT = Number(process.env.MONIK_LOCAL_SCAN_PORT || 6668);
const DEFAULT_SCAN_TIMEOUT_MS = Number(process.env.MONIK_LOCAL_SCAN_TIMEOUT_MS || 350);
const DEFAULT_PING_TIMEOUT_MS = Number(process.env.MONIK_LOCAL_PING_TIMEOUT_MS || 250);
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


async function runCommand(command, args) {
  try {
    const { stdout } = await execFileAsync(command, args, { timeout: 5000, windowsHide: true });
    return stdout;
  } catch {
    return '';
  }
}

function normalizeMac(mac = '') {
  const normalized = String(mac).trim().replaceAll('-', ':').toLowerCase();
  return /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/.test(normalized) ? normalized : null;
}

function parseArpOutput(output = '') {
  const entries = new Map();
  const ipv4Pattern = /(?:\d{1,3}\.){3}\d{1,3}/g;
  const macPattern = /(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}/ig;

  for (const line of output.split(/\r?\n/)) {
    const ip = line.match(ipv4Pattern)?.[0];
    const mac = normalizeMac(line.match(macPattern)?.[0]);
    if (ip && mac) entries.set(ip, mac);
  }

  return entries;
}

async function readMacTable() {
  const outputs = await Promise.all([
    runCommand('arp', ['-a']),
    platform() === 'win32' ? '' : runCommand('ip', ['neigh']),
  ]);
  const table = new Map();

  for (const output of outputs) {
    for (const [ip, mac] of parseArpOutput(output)) {
      table.set(ip, mac);
    }
  }

  return table;
}

async function pingHost(host, timeoutMs) {
  const isWindows = platform() === 'win32';
  const args = isWindows
    ? ['-n', '1', '-w', String(timeoutMs), host]
    : ['-c', '1', '-W', String(Math.max(1, Math.ceil(timeoutMs / 1000))), host];
  const output = await runCommand('ping', args);
  return output.length > 0 && !/unreachable|timed out|100% packet loss/i.test(output);
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

async function scanLan({ port = DEFAULT_SCAN_PORT, timeoutMs = DEFAULT_SCAN_TIMEOUT_MS, pingTimeoutMs = DEFAULT_PING_TIMEOUT_MS, limit = 254, concurrency = 64 } = {}) {
  const prefixes = getLocalPrefixes();
  const hosts = hostsFromPrefixes(prefixes, limit);
  const portOpen = [];
  const seen = new Set();
  let cursor = 0;

  async function worker() {
    while (cursor < hosts.length) {
      const host = hosts[cursor];
      cursor += 1;
      const [portResult] = await Promise.all([
        probePort(host, port, timeoutMs),
        pingHost(host, pingTimeoutMs),
      ]);
      if (portResult.open) portOpen.push(portResult);
      seen.add(host);
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, hosts.length || 1) }, worker));

  const macTable = await readMacTable();
  const discoveredMap = new Map();
  for (const host of seen) {
    const mac = macTable.get(host) || null;
    const hasOpenPort = portOpen.some((entry) => entry.ip === host);
    if (mac || hasOpenPort) {
      discoveredMap.set(host, { ip: host, mac, port, port6668Open: hasOpenPort });
    }
  }

  for (const [ip, mac] of macTable) {
    if (!discoveredMap.has(ip) && hosts.includes(ip)) {
      discoveredMap.set(ip, { ip, mac, port, port6668Open: false });
    }
  }

  return {
    port,
    prefixes,
    scannedHosts: hosts.length,
    open: portOpen,
    discoveredHosts: [...discoveredMap.values()].sort((left, right) => left.ip.localeCompare(right.ip, undefined, { numeric: true })),
  };
}

function buildLocalControlList({ stratoDevices, yandexDevices, discoveredHosts, port }) {
  const hostsByIp = new Map(discoveredHosts.map((host) => [host.ip, host]));

  return stratoDevices.map((device) => {
    const matchedYandex = yandexDevices.find((candidate) => sameDevice(device, candidate)) || null;
    const localIp = device.localIp || matchedYandex?.localIp || null;
    const discoveredHost = localIp ? hostsByIp.get(localIp) : null;
    const portOpen = Boolean(discoveredHost?.port6668Open);

    return {
      id: device.id,
      name: device.name,
      localIp,
      mac: discoveredHost?.mac || null,
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
  }).filter((device) => device.localIp || device.mac || device.localKey || device.port6668Open);
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
    scanLan(options.scan),
  ]);

  const localDevices = buildLocalControlList({
    stratoDevices: stratoSnapshot.devices,
    yandexDevices: yandexSnapshot.devices,
    discoveredHosts: localScan.discoveredHosts,
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

function inferChannelCount(device, capabilities) {
  const onOffCapabilities = capabilities.filter((capability) => String(capability.type || '').includes('on_off'));
  const channelInstances = onOffCapabilities
    .map((capability) => capability.state?.instance || capability.parameters?.instance || capability.instance)
    .filter(Boolean);
  const numberedChannels = channelInstances
    .map((instance) => String(instance).match(/(?:channel|switch|outlet|relay|gang)[_-]?(\d+)/i)?.[1])
    .filter(Boolean)
    .map(Number);

  if (numberedChannels.length > 0) return Math.max(...numberedChannels);
  if (onOffCapabilities.length > 1) return onOffCapabilities.length;

  const name = `${device.name || ''} ${device.raw?.name || ''}`;
  if (/\b(дву|double|2[ -]?gang|two)\b/i.test(name)) return 2;
  if (/\b(три|triple|3[ -]?gang|three)\b/i.test(name)) return 3;
  if (/\b(четири|quad|4[ -]?gang|four)\b/i.test(name)) return 4;
  return 1;
}

function actionTemplate(type, instance, value) {
  return {
    type,
    state: {
      instance,
      value,
    },
  };
}

function rangeValues(parameters = {}, instance = '') {
  const range = parameters.range || {};
  const min = Number.isFinite(range.min) ? range.min : 0;
  const max = Number.isFinite(range.max) ? range.max : instance === 'brightness' ? 100 : 1;
  const middle = Math.round((min + max) / 2);
  return [...new Set([min, middle, max])];
}

function buildCapabilityControls(capability = {}) {
  const type = capability.type || 'unknown';
  const parameters = capability.parameters || {};
  const state = capability.state || {};
  const instance = state.instance || parameters.instance || capability.instance || 'default';

  if (String(type).includes('on_off')) {
    return [
      { label: 'ON JSON', safe: true, command: actionTemplate(type, 'on', true) },
      { label: 'OFF JSON', safe: true, command: actionTemplate(type, 'on', false) },
    ];
  }

  if (String(type).includes('range')) {
    return rangeValues(parameters, instance).map((value) => ({
      label: `${instance}=${value}`,
      safe: true,
      command: actionTemplate(type, instance, value),
    }));
  }

  if (String(type).includes('mode')) {
    return (parameters.modes || []).map((mode) => ({
      label: `${instance}:${mode.value}`,
      safe: true,
      command: actionTemplate(type, instance, mode.value),
    }));
  }

  if (String(type).includes('toggle')) {
    return [
      { label: `${instance}=true`, safe: true, command: actionTemplate(type, instance, true) },
      { label: `${instance}=false`, safe: true, command: actionTemplate(type, instance, false) },
    ];
  }

  if (String(type).includes('color_setting')) {
    const controls = [];
    if (parameters.color_model) controls.push({ label: 'RGB sample JSON', safe: true, command: actionTemplate(type, 'rgb', 16777215) });
    if (parameters.temperature_k) controls.push({ label: 'temperature_k JSON', safe: true, command: actionTemplate(type, 'temperature_k', parameters.temperature_k.min || 2700) });
    return controls;
  }

  return [];
}

function buildLocalCommandTemplates({ device, localMatch, channelCount }) {
  if (!localMatch?.localKey && !localMatch?.localIp) return [];

  return Array.from({ length: channelCount }, (_, index) => {
    const dpsIndex = String(index + 1);
    return {
      channel: index + 1,
      on: {
        protocol: 'tuya-local',
        safePreviewOnly: true,
        ip: localMatch.localIp,
        mac: localMatch.mac || null,
        deviceId: device.id,
        localKey: localMatch.localKey || '<въведи-local-key-ръчно>',
        dps: { [dpsIndex]: true },
      },
      off: {
        protocol: 'tuya-local',
        safePreviewOnly: true,
        ip: localMatch.localIp,
        mac: localMatch.mac || null,
        deviceId: device.id,
        localKey: localMatch.localKey || '<въведи-local-key-ръчно>',
        dps: { [dpsIndex]: false },
      },
    };
  });
}


function buildLocalHostCommandTemplates(host, channelCount = 1) {
  return Array.from({ length: channelCount }, (_, index) => {
    const dpsIndex = String(index + 1);
    const base = {
      protocol: 'tuya-local',
      safePreviewOnly: true,
      ip: host.ip,
      mac: host.mac || null,
      deviceId: `lan:${host.ip}`,
      localKey: '<въведи-local-key-ръчно>',
    };

    return {
      channel: index + 1,
      on: { ...base, dps: { [dpsIndex]: true } },
      off: { ...base, dps: { [dpsIndex]: false } },
    };
  });
}

function fallbackOnOffCapability() {
  return {
    type: 'devices.capabilities.on_off',
    instance: 'on',
    retrievable: false,
    reportable: false,
    parameters: {},
    state: null,
    testButtons: buildCapabilityControls({ type: 'devices.capabilities.on_off', state: { instance: 'on' } }),
    fallback: true,
  };
}

function findLocalMatch(device, localDevices, discoveredHosts) {
  const fromLocalDevices = localDevices.find((candidate) => candidate.id === device.id || candidate.name === device.name || candidate.localIp === device.localIp);
  if (fromLocalDevices) return fromLocalDevices;

  const rawIp = device.raw?.localIp || device.raw?.local_ip || device.raw?.ip || device.localIp;
  const host = rawIp ? discoveredHosts.find((candidate) => candidate.ip === rawIp) : null;
  return host ? { localIp: host.ip, mac: host.mac, port6668Open: host.port6668Open, localKey: device.localKey || null } : null;
}

export async function runYandexRawSchemaScan(options = {}) {
  const scan = await runReadOnlyWebScan(options);
  const yandexPayload = scan.yandex.configured
    ? (await fetchJsonSnapshot({
        url: options.yandexUrl ?? process.env.MONIK_YANDEX_DEVICES_URL,
        token: options.yandexToken ?? process.env.MONIK_YANDEX_ACCESS_TOKEN,
        label: 'yandex',
      })).payload
    : null;
  const yandexDevices = yandexPayload ? normalizeSnapshot(yandexPayload, 'yandex') : [];
  const schemaDevices = yandexDevices.map((device) => {
    const rawCapabilities = Array.isArray(device.raw?.capabilities) ? device.raw.capabilities : [];
    const rawProperties = Array.isArray(device.raw?.properties) ? device.raw.properties : [];
    const localMatch = findLocalMatch(device, scan.localDevices, scan.localScan.discoveredHosts);
    const channelCount = inferChannelCount(device, rawCapabilities);

    return {
      id: device.id,
      name: device.name,
      type: device.raw?.type || device.category || null,
      isLocalFirst: Boolean(localMatch?.port6668Open || localMatch?.localKey || localMatch?.localIp),
      local: localMatch || null,
      channelCount,
      capabilities: (rawCapabilities.length > 0 ? rawCapabilities.map((capability) => ({
        type: capability.type || 'unknown',
        instance: capability.state?.instance || capability.parameters?.instance || capability.instance || null,
        retrievable: Boolean(capability.retrievable),
        reportable: Boolean(capability.reportable),
        parameters: capability.parameters || {},
        state: capability.state || null,
        testButtons: buildCapabilityControls(capability),
      })) : [fallbackOnOffCapability()]),
      properties: rawProperties.map((property) => ({
        type: property.type || 'unknown',
        instance: property.state?.instance || property.parameters?.instance || property.instance || null,
        retrievable: Boolean(property.retrievable),
        reportable: Boolean(property.reportable),
        parameters: property.parameters || {},
        state: property.state || null,
      })),
      localCommandJson: buildLocalCommandTemplates({ device, localMatch, channelCount }),
      raw: device.raw,
    };
  }).sort((left, right) => Number(right.isLocalFirst) - Number(left.isLocalFirst));

  const localOnlyDevices = scan.localDevices
    .filter((device) => !schemaDevices.some((schemaDevice) => schemaDevice.id === device.id || schemaDevice.local?.localIp === device.localIp))
    .map((device) => {
      const localMatch = {
        localIp: device.localIp,
        mac: device.mac,
        port6668Open: device.port6668Open,
        localKey: device.localKey,
      };

      return {
        id: device.id,
        name: device.name,
        type: device.category || 'strato/local',
        isLocalFirst: true,
        local: localMatch,
        capabilities: [fallbackOnOffCapability()],
        properties: [],
        channelCount: 1,
        localCommandJson: buildLocalCommandTemplates({ device, localMatch, channelCount: 1 }),
        raw: device.raw || device,
      };
    });

  const knownLocalIps = new Set([...schemaDevices, ...localOnlyDevices].map((device) => device.local?.localIp).filter(Boolean));
  const localOnlyHosts = scan.localScan.discoveredHosts
    .filter((host) => !knownLocalIps.has(host.ip))
    .map((host) => ({
      id: `lan:${host.ip}`,
      name: `LAN ${host.ip}`,
      type: 'lan/port-scan',
      isLocalFirst: true,
      local: { localIp: host.ip, mac: host.mac, port6668Open: host.port6668Open, localKey: null },
      capabilities: [fallbackOnOffCapability()],
      properties: [],
      channelCount: 1,
      localCommandJson: buildLocalHostCommandTemplates(host, 1),
      raw: host,
    }));

  return {
    readOnly: true,
    writesPerformed: false,
    commandsExecuted: false,
    yandexConfigured: scan.yandex.configured,
    yandexRaw: yandexPayload,
    localScan: scan.localScan,
    devices: [...localOnlyDevices, ...localOnlyHosts, ...schemaDevices],
    notes: [
      'RAW Yandex read is GET only.',
      'Schema buttons are JSON previews only; this endpoint does not send device commands.',
      'Local command JSON is generated for manual testing by the user only.',
    ],
  };
}
