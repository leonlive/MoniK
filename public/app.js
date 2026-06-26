const form = document.querySelector('#tuyaLinkForm');
const resultBox = document.querySelector('#resultBox');
const serverStatus = document.querySelector('#serverStatus');
const countryCodeInput = document.querySelector('#countryCode');
const schemaInput = document.querySelector('#schema');
const clearResultButton = document.querySelector('#clearResult');

function showResult(payload, state = '') {
  resultBox.className = state;
  resultBox.textContent = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
}

async function loadServerConfig() {
  try {
    const response = await fetch('/api/tuya/config');
    const config = await response.json();

    countryCodeInput.value = config.countryCode || '49';
    schemaInput.value = config.schema || 'tuyaSmart';
    serverStatus.textContent = `online · ${config.baseUrl}`;
    serverStatus.className = 'is-success';
  } catch (error) {
    serverStatus.textContent = `offline · ${error.message}`;
    serverStatus.className = 'is-error';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const submitButton = form.querySelector('button[type="submit"]');
  const formData = new FormData(form);
  const body = Object.fromEntries(formData.entries());

  submitButton.disabled = true;
  showResult('MoniK server изпраща заявка към Tuya SDK. Моля изчакай...', '');

  try {
    const response = await fetch('/api/tuya/link', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    const payload = await response.json();

    showResult(payload, response.ok ? 'is-success' : 'is-error');
  } catch (error) {
    showResult({ linked: false, error: error.message }, 'is-error');
  } finally {
    submitButton.disabled = false;
  }
});

clearResultButton.addEventListener('click', () => {
  showResult('Готово за реален Tuya login.');
});

loadServerConfig();
