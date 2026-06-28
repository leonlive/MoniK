const form = document.querySelector('#deviceImportForm');
const resultBox = document.querySelector('#resultBox');
const serverStatus = document.querySelector('#serverStatus');
const pairingBox = document.querySelector('#pairingBox');
const pairingCodeInput = document.querySelector('#pairingCode');
const clearResultButton = document.querySelector('#clearResult');

function showResult(payload, state = '') {
  resultBox.className = state;
  resultBox.textContent = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
}

function renderPairing(pairing) {
  pairingCodeInput.value = pairing.pairingCode;
  pairingBox.innerHTML = `
    <p><strong>Код за връзка:</strong> <code>${pairing.pairingCode}</code></p>
    <p><strong>Телефонът трябва да е на същия Wi‑Fi.</strong> В MoniK Android app въведи един от тези адреси:</p>
    <ul>
      ${pairing.importEndpoints.map((endpoint) => `<li><code>${endpoint}</code></li>`).join('')}
    </ul>
  `;
}

async function loadServerStatus() {
  try {
    const response = await fetch('/health');
    const status = await response.json();
    const pairingResponse = await fetch('/api/monik/pairing');
    const pairing = await pairingResponse.json();

    serverStatus.textContent = `online · ${status.mode}`;
    serverStatus.className = 'is-success';
    renderPairing(pairing);
  } catch (error) {
    serverStatus.textContent = `offline · ${error.message}`;
    serverStatus.className = 'is-error';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const submitButton = form.querySelector('button[type="submit"]');
  const formData = new FormData(form);
  const devicesJson = formData.get('devicesJson');
  const pairingCode = formData.get('pairingCode');

  submitButton.disabled = true;
  showResult('MoniK server приема устройства от mobile SDK клиента...', '');

  try {
    const response = await fetch('/api/monik/devices/import', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-monik-pairing-code': pairingCode,
      },
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

clearResultButton.addEventListener('click', () => {
  showResult('Готово за реален SDK import. Няма developer credentials в този server.');
});

loadServerStatus();
