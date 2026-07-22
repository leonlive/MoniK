const adbForm = document.querySelector('#adbImportForm');
const jsonForm = document.querySelector('#deviceImportForm');
const resultBox = document.querySelector('#resultBox');
const serverStatus = document.querySelector('#serverStatus');
const adbStatusBox = document.querySelector('#adbStatusBox');
const packageNameInput = document.querySelector('#packageName');
const deviceFileInput = document.querySelector('#deviceFile');
const clearResultButton = document.querySelector('#clearResult');
const clearLogcatButton = document.querySelector('#clearLogcat');
const readLogcatButton = document.querySelector('#readLogcat');
const runWebScanButton = document.querySelector('#runWebScan');
const buildYandexSchemaButton = document.querySelector('#buildYandexSchema');
const schemaTable = document.querySelector('#schemaTable');


function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}


async function sendCommand(endpoint, command) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(command),
  });
  const payload = await response.json();
  showResult(payload, response.ok ? 'is-success' : 'is-error');
}

function commandWithManualLocalKey(command) {
  if (command.localKey && !String(command.localKey).includes('въведи-local-key')) return command;
  const localKey = window.prompt('Въведи localKey за това устройство:');
  if (!localKey) return null;
  return { ...command, localKey };
}

function renderSchema(payload) {
  if (!payload.devices?.length) {
    schemaTable.innerHTML = '<p class="is-error">Няма Yandex devices. Провери MONIK_YANDEX_DEVICES_URL / token. LAN hosts са в JSON отговора.</p>';
    return;
  }

  schemaTable.innerHTML = payload.devices.map((device, index) => {
    const local = device.local ? `${device.local.localIp || '-'} · ${device.local.mac || 'no-mac'} · ${device.local.port6668Open ? '6668 open' : '6668 closed/unknown'}` : 'няма local match';
    const capabilities = device.capabilities.map((capability) => `
      <li>
        <strong>${escapeHtml(capability.type)}</strong> ${capability.instance ? `· <code>${escapeHtml(capability.instance)}</code>` : ''}
        <div class="button-row">
          ${capability.testButtons.map((button) => {
            const command = { deviceId: device.id, action: button.command };
            return `
              <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify(command, null, 2))}">JSON ${escapeHtml(button.label)}</button>
              <button class="real-command yandex-command" type="button" data-json="${escapeHtml(JSON.stringify(command))}">ИЗПЪЛНИ ${escapeHtml(button.label)}</button>
            `;
          }).join('')}
        </div>
      </li>
    `).join('');
    const localCommands = device.localCommandJson.map((command) => `
      <div class="button-row">
        <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify(command.on, null, 2))}">Local ch.${command.channel} ON JSON</button>
        <button class="real-command local-command" type="button" data-json="${escapeHtml(JSON.stringify(command.on))}">ИЗПЪЛНИ Local ch.${command.channel} ON</button>
        <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify(command.off, null, 2))}">Local ch.${command.channel} OFF JSON</button>
        <button class="real-command local-command" type="button" data-json="${escapeHtml(JSON.stringify(command.off))}">ИЗПЪЛНИ Local ch.${command.channel} OFF</button>
      </div>
    `).join('');

    return `
      <article class="schema-card ${device.isLocalFirst ? 'local-first' : ''}">
        <h3>${index + 1}. ${escapeHtml(device.name)} ${device.isLocalFirst ? '<span>LOCAL</span>' : ''}</h3>
        <p><strong>ID:</strong> <code>${escapeHtml(device.id)}</code></p>
        <p><strong>Type:</strong> ${escapeHtml(device.type || '-')} · <strong>Channels:</strong> ${escapeHtml(device.channelCount || 1)}</p>
        <p><strong>Local:</strong> ${escapeHtml(local)}</p>
        <details open>
          <summary>Capabilities / тест JSON бутони</summary>
          <ul>${capabilities || '<li>Няма capabilities в RAW.</li>'}</ul>
        </details>
        <details>
          <summary>Локални command JSON бутони</summary>
          ${localCommands || '<p>Няма local IP/key match. Можеш да добавиш local key ръчно по JSON шаблона след като имаме IP/device mapping.</p>'}
        </details>
        <details>
          <summary>RAW device JSON</summary>
          <pre>${escapeHtml(JSON.stringify(device.raw, null, 2))}</pre>
        </details>
      </article>
    `;
  }).join('');

  schemaTable.querySelectorAll('.json-preview').forEach((button) => {
    button.addEventListener('click', () => showResult(button.dataset.json, 'is-success'));
  });
  schemaTable.querySelectorAll('.yandex-command').forEach((button) => {
    button.addEventListener('click', () => sendCommand('/api/monik/yandex-command', JSON.parse(button.dataset.json)));
  });
  schemaTable.querySelectorAll('.local-command').forEach((button) => {
    button.addEventListener('click', () => {
      const command = commandWithManualLocalKey(JSON.parse(button.dataset.json));
      if (command) sendCommand('/api/monik/local-command', command);
    });
  });
}

function renderWebScan(payload) {
  const hosts = payload.localScan?.discoveredHosts || [];
  const devices = payload.localDevices || [];
  const hostRows = hosts.map((host) => `
    <tr>
      <td><code>${escapeHtml(host.ip)}</code></td>
      <td>${escapeHtml(host.mac || 'няма MAC от ARP')}</td>
      <td>${host.port6668Open ? '<span class="is-success">OPEN</span>' : '<span class="is-error">closed/unknown</span>'}</td>
    </tr>
  `).join('');
  const deviceCards = devices.map((device) => {
    const localKeyText = device.localKey ? 'има local key от snapshot' : 'няма local key — ще го поиска ръчно';
    const onCommand = device.control?.on || {
      protocol: 'tuya-local',
      ip: device.localIp,
      mac: device.mac,
      port: payload.localScan?.port || 6668,
      deviceId: device.id,
      localKey: '<въведи-local-key-ръчно>',
      dps: { 1: true },
    };
    const offCommand = device.control?.off || { ...onCommand, dps: { 1: false } };

    return `
      <article class="schema-card local-first">
        <h3>${escapeHtml(device.name)} <span>LOCAL</span></h3>
        <p><strong>ID:</strong> <code>${escapeHtml(device.id)}</code></p>
        <p><strong>IP:</strong> <code>${escapeHtml(device.localIp || '-')}</code> · <strong>MAC:</strong> ${escapeHtml(device.mac || 'няма')}</p>
        <p><strong>6668:</strong> ${device.port6668Open ? 'open' : 'closed/unknown'} · <strong>Key:</strong> ${escapeHtml(localKeyText)}</p>
        <div class="button-row">
          <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify(onCommand, null, 2))}">Local ON JSON</button>
          <button class="real-command local-command" type="button" data-json="${escapeHtml(JSON.stringify(onCommand))}">ИЗПЪЛНИ Local ON</button>
          <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify(offCommand, null, 2))}">Local OFF JSON</button>
          <button class="real-command local-command" type="button" data-json="${escapeHtml(JSON.stringify(offCommand))}">ИЗПЪЛНИ Local OFF</button>
        </div>
        <details><summary>RAW local device</summary><pre>${escapeHtml(JSON.stringify(device, null, 2))}</pre></details>
      </article>
    `;
  }).join('');

  schemaTable.innerHTML = `
    <div class="scan-summary">
      <strong>LAN scan:</strong>
      ${escapeHtml(payload.localScan?.scannedHosts || 0)} hosts ·
      ${escapeHtml(hosts.length)} IP/MAC rows ·
      ${escapeHtml(hosts.filter((host) => host.port6668Open).length)} hosts with 6668 open ·
      ${escapeHtml(devices.length)} mapped local devices
    </div>
    ${deviceCards || '<p class="is-error">Няма mapped local devices от Strato/Yandex snapshot. По-долу показвам суровите IP/MAC hosts от LAN scan.</p>'}
    <details open>
      <summary>IP + MAC таблица от локалния scanner</summary>
      <table class="scan-table">
        <thead><tr><th>IP</th><th>MAC</th><th>Tuya 6668</th></tr></thead>
        <tbody>${hostRows || '<tr><td colspan="3">Няма ARP/6668 резултати. Задай MONIK_LOCAL_SCAN_CIDR към правилната LAN мрежа.</td></tr>'}</tbody>
      </table>
    </details>
  `;

  schemaTable.querySelectorAll('.json-preview').forEach((button) => {
    button.addEventListener('click', () => showResult(button.dataset.json, 'is-success'));
  });
  schemaTable.querySelectorAll('.local-command').forEach((button) => {
    button.addEventListener('click', () => {
      const command = commandWithManualLocalKey(JSON.parse(button.dataset.json));
      if (command) sendCommand('/api/monik/local-command', command);
    });
  });
}

function showResult(payload, state = '') {
  resultBox.className = state;
  resultBox.textContent = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
}

function renderAdbStatus(status) {
  packageNameInput.value = status.defaultPackage;
  deviceFileInput.value = status.defaultDeviceFile;

  if (!status.adbAvailable) {
    adbStatusBox.innerHTML = `<p class="is-error">ADB не е достъпен: ${status.error}</p>`;
    return;
  }

  adbStatusBox.innerHTML = `
    <p class="is-success">ADB е достъпен.</p>
    <p><strong>Devices:</strong></p>
    <ul>${status.devices.map((device) => `<li><code>${device.serial}</code> · ${device.state}</li>`).join('')}</ul>
  `;
}

async function loadStatus() {
  try {
    const response = await fetch('/health');
    const status = await response.json();
    const adbResponse = await fetch('/api/monik/adb/status');
    const adbStatus = await adbResponse.json();

    serverStatus.textContent = `online · ${status.mode}`;
    serverStatus.className = 'is-success';
    renderAdbStatus(adbStatus);
  } catch (error) {
    serverStatus.textContent = `offline · ${error.message}`;
    serverStatus.className = 'is-error';
  }
}

adbForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const submitButton = adbForm.querySelector('button[type="submit"]');
  const body = Object.fromEntries(new FormData(adbForm).entries());

  submitButton.disabled = true;
  showResult('MoniK server чете devices export от телефона през ADB...', '');

  try {
    const response = await fetch('/api/monik/adb/import', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    const payload = await response.json();

    showResult(payload, response.ok ? 'is-success' : 'is-error');
    if (response.ok) schemaTable.innerHTML = '<p class="is-success">JSON файлът е зареден. Натисни “Сканирай само WEB / read-only” или “Вземи Yandex RAW и построи схема”, за да се сравни със LAN scan-а.</p>';
  } catch (error) {
    showResult({ imported: false, error: error.message }, 'is-error');
  } finally {
    submitButton.disabled = false;
  }
});

jsonForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const submitButton = jsonForm.querySelector('button[type="submit"]');
  const formData = new FormData(jsonForm);
  const devicesFile = formData.get('devicesFile');
  const pastedJson = formData.get('devicesJson');
  const devicesJson = devicesFile && devicesFile.size > 0 ? await devicesFile.text() : pastedJson;

  if (!devicesJson?.trim()) {
    showResult({ imported: false, error: 'Избери JSON файл или paste-ни JSON.' }, 'is-error');
    return;
  }

  submitButton.disabled = true;
  showResult('MoniK server приема пълното Tuya sharing JSON copy...', '');

  try {
    const response = await fetch('/api/monik/devices/import', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: devicesJson,
    });
    const payload = await response.json();

    showResult(payload, response.ok ? 'is-success' : 'is-error');
    if (response.ok) schemaTable.innerHTML = '<p class="is-success">Пълното Tuya sharing JSON copy е заредено. Натисни “Сканирай само WEB / read-only”, за да се сравнят ID/IP/localKey стойностите със LAN scan-а.</p>';
  } catch (error) {
    showResult({ imported: false, error: error.message }, 'is-error');
  } finally {
    submitButton.disabled = false;
  }
});




buildYandexSchemaButton.addEventListener('click', async () => {
  buildYandexSchemaButton.disabled = true;
  schemaTable.innerHTML = '<p>Чета Yandex RAW read-only и строя схема...</p>';
  showResult('Yandex RAW schema build: само GET/status/info, без device commands...', '');

  try {
    const response = await fetch('/api/monik/yandex-schema', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    });
    const payload = await response.json();
    renderSchema(payload);
    showResult(payload, response.ok ? 'is-success' : 'is-error');
  } catch (error) {
    const payload = { readOnly: true, commandsExecuted: false, error: error.message };
    schemaTable.innerHTML = `<p class="is-error">${escapeHtml(error.message)}</p>`;
    showResult(payload, 'is-error');
  } finally {
    buildYandexSchemaButton.disabled = false;
  }
});

runWebScanButton.addEventListener('click', async () => {
  runWebScanButton.disabled = true;
  schemaTable.innerHTML = '<p>Сканирам LAN + чета snapshot-и read-only...</p>';
  showResult('Read-only WEB scan: Yandex + Strato + LAN 6668...', '');

  try {
    const response = await fetch('/api/monik/web-scan', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    });
    const payload = await response.json();
    renderWebScan(payload);
    showResult(payload, response.ok ? 'is-success' : 'is-error');
  } catch (error) {
    schemaTable.innerHTML = `<p class="is-error">${escapeHtml(error.message)}</p>`;
    showResult({ readOnly: true, writesPerformed: false, error: error.message }, 'is-error');
  } finally {
    runWebScanButton.disabled = false;
  }
});

clearLogcatButton.addEventListener('click', async () => {
  showResult('Изчистване на ADB logcat...', '');

  try {
    const response = await fetch('/api/monik/adb/logcat/clear', { method: 'POST' });
    const payload = await response.json();
    showResult(payload, response.ok ? 'is-success' : 'is-error');
  } catch (error) {
    showResult({ cleared: false, error: error.message }, 'is-error');
  }
});

readLogcatButton.addEventListener('click', async () => {
  showResult('Четене на ADB logcat...', '');

  try {
    const filter = encodeURIComponent('tuya smartlife thing kt login error success false schema country client account home device bridge native method');
    const response = await fetch(`/api/monik/adb/logcat?lines=1200&filter=${filter}`);
    const payload = await response.json();
    showResult(payload, response.ok ? 'is-success' : 'is-error');
  } catch (error) {
    showResult({ logcat: false, error: error.message }, 'is-error');
  }
});

clearResultButton.addEventListener('click', () => {
  showResult('Готово за ADB import от телефона.');
});

loadStatus();
