export class CommandError extends Error {
  constructor(message, statusCode = 400, details = {}) {
    super(message);
    this.name = 'CommandError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

function requireUrl(url, name) {
  if (!url) throw new CommandError(`${name} is not configured. Command was not sent.`, 400, { missing: name });
  return url;
}

async function postJson(url, payload, headers = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'content-type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  let body = null;

  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { raw: text };
  }

  return {
    ok: response.ok,
    status: response.status,
    body,
  };
}

export async function sendYandexCommand(command = {}, env = process.env) {
  const url = requireUrl(env.MONIK_YANDEX_ACTION_URL, 'MONIK_YANDEX_ACTION_URL');
  const headers = {};
  if (env.MONIK_YANDEX_ACCESS_TOKEN) headers.authorization = `Bearer ${env.MONIK_YANDEX_ACCESS_TOKEN}`;

  const upstream = await postJson(url, command, headers);
  return {
    commandSent: true,
    target: 'yandex',
    upstream,
  };
}

export async function sendLocalCommand(command = {}, env = process.env) {
  const url = requireUrl(env.MONIK_LOCAL_COMMAND_URL, 'MONIK_LOCAL_COMMAND_URL');
  if (!command.localKey || String(command.localKey).includes('въведи-local-key')) {
    throw new CommandError('localKey is required before sending local command.', 400, { missing: 'localKey' });
  }

  const upstream = await postJson(url, command);
  return {
    commandSent: true,
    target: 'local',
    upstream,
  };
}
