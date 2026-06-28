import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const DEFAULT_PACKAGE = process.env.MONIK_ANDROID_PACKAGE || 'com.monik.app';
const DEFAULT_DEVICE_FILE = process.env.MONIK_TUYA_EXPORT_FILE || 'files/monik_tuya_devices.json';

export class AdbBridgeError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'AdbBridgeError';
    this.details = details;
  }
}

async function adb(args) {
  try {
    const { stdout } = await execFileAsync('adb', args, { windowsHide: true, timeout: 15000 });
    return stdout.trim();
  } catch (error) {
    throw new AdbBridgeError('ADB command failed.', {
      command: `adb ${args.join(' ')}`,
      message: error.message,
      stderr: error.stderr,
    });
  }
}

export async function getAdbStatus() {
  try {
    const output = await adb(['devices']);
    const devices = output
      .split('\n')
      .slice(1)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [serial, state] = line.split(/\s+/);
        return { serial, state };
      });

    return {
      adbAvailable: true,
      defaultPackage: DEFAULT_PACKAGE,
      defaultDeviceFile: DEFAULT_DEVICE_FILE,
      devices,
    };
  } catch (error) {
    return {
      adbAvailable: false,
      defaultPackage: DEFAULT_PACKAGE,
      defaultDeviceFile: DEFAULT_DEVICE_FILE,
      error: error.message,
      details: error.details,
    };
  }
}

export async function readMonikTuyaExport({ packageName = DEFAULT_PACKAGE, deviceFile = DEFAULT_DEVICE_FILE } = {}) {
  if (!packageName) {
    throw new AdbBridgeError('Android package name is required.');
  }

  if (!deviceFile) {
    throw new AdbBridgeError('Device export file path is required.');
  }

  const output = await adb(['shell', 'run-as', packageName, 'cat', deviceFile]);

  try {
    return JSON.parse(output);
  } catch (error) {
    throw new AdbBridgeError('ADB export file did not contain valid JSON.', {
      packageName,
      deviceFile,
      message: error.message,
      outputPreview: output.slice(0, 500),
    });
  }
}

export async function clearAdbLogcat() {
  await adb(['logcat', '-c']);
  return { cleared: true };
}

export async function readAdbLogcat({ lines = 600, filter = '' } = {}) {
  const safeLines = String(Math.max(50, Math.min(Number(lines) || 600, 5000)));
  const output = await adb(['logcat', '-d', '-t', safeLines]);
  const normalizedFilter = String(filter || '').trim().toLowerCase();
  const text = normalizedFilter
    ? output
        .split('\n')
        .filter((line) => line.toLowerCase().includes(normalizedFilter))
        .join('\n')
    : output;

  return {
    filter: normalizedFilter || null,
    lines: Number(safeLines),
    text,
  };
}
