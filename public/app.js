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
          ${capability.testButtons.map((button) => `
            <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify({ deviceId: device.id, action: button.command }, null, 2))}">${escapeHtml(button.label)}</button>
          `).join('')}
        </div>
      </li>
    `).join('');
    const localCommands = device.localCommandJson.map((command) => `
      <div class="button-row">
        <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify(command.on, null, 2))}">Local ch.${command.channel} ON JSON</button>
        <button class="secondary-button json-preview" type="button" data-json="${escapeHtml(JSON.stringify(command.off, null, 2))}">Local ch.${command.channel} OFF JSON</button>
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
  } catch (error) {
    showResult({ imported: false, error: error.message }, 'is-error');
  } finally {
    submitButton.disabled = false;
  }
});

jsonForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const submitButton = jsonForm.querySelector('button[type="submit"]');
  const devicesJson = new FormData(jsonForm).get('devicesJson');

  submitButton.disabled = true;
  showResult('MoniK server приема JSON export...', '');

  try {
    const response = await fetch('/api/monik/devices/import', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: devicesJson,
    });
    const payload = await response.json();

    showResult(payload, response.ok ? 'is-success' : 'is-error');
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
  showResult('Read-only WEB scan: Yandex + Strato + LAN 6668...', '');

  try {
    const response = await fetch('/api/monik/web-scan', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    });
    const payload = await response.json();
    showResult(payload, response.ok ? 'is-success' : 'is-error');
  } catch (error) {
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
