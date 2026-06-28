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
