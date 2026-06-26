# MoniK Tuya Link

Това звено е за **free user flow**: крайният потребител използва вече съществуващ Tuya акаунт. Не искаме от него Tuya developer акаунт, Access ID или Secret.

Важно разграничение:

- **Потребителят** въвежда само Tuya username/email/телефон и парола на страницата.
- **MoniK server** държи connector настройките към Tuya и изпълнява login/import заявките.
- Ако тестваш локално без готов MoniK backend, трябва временно да пуснеш MoniK server с MoniK connector ключове. Това не са ключове на крайния потребител.

## Най-бърз тест от твоя компютър

Да, за локален тест трябва да свалиш кода, защото страницата говори с локален MoniK server (`npm start`). Не може само директно от GitHub web страницата, защото GitHub не стартира Node.js server.

### 1. Инсталирай нужните неща

- Node.js 20 LTS или по-нова версия: <https://nodejs.org>
- Git: <https://git-scm.com/downloads>

Провери в terminal / PowerShell:

```bash
node -v
npm -v
git --version
```

### 2. Свали repo-то

```bash
git clone <REPO_URL>
cd MoniK
npm install
```

Ако вече си го свалил:

```bash
cd MoniK
git pull
npm install
```

### 3. Настрой MoniK server connector-а

За production/free user версията това се настройва само на MoniK server-а, не от крайния потребител.
За локален standalone тест копирай `.env.example` в `.env` и попълни MoniK connector стойностите:

```bash
cp .env.example .env
```

В `.env`:

```bash
MONIK_TUYA_ACCESS_ID=monik-server-access-id
MONIK_TUYA_ACCESS_SECRET=monik-server-access-secret
TUYA_DATA_CENTER=eu
TUYA_COUNTRY_CODE=49
TUYA_SCHEMA=tuyaSmart
PORT=4173
```

Важно:

- Крайният user не попълва тези стойности. Те са server-side настройки за MoniK connector-а.
- `TUYA_COUNTRY_CODE=49` е default за international login.
- На тест страницата има и `359 · България`, ако трябва да пробваш с България.
- `TUYA_DATA_CENTER` трябва да съвпада с MoniK/Tuya connector настройката: `eu`, `us`, `cn`, `in`, `ea` или `we`.

### 4. Стартирай MoniK server

```bash
npm start
```

Когато видиш:

```text
MoniK Tuya link server listening on http://localhost:4173
```

отвори в browser:

```text
http://localhost:4173
```

Там въвеждаш само реален Tuya username/email/телефон и Tuya парола. Формата праща `POST /api/tuya/link`, MoniK server прави Tuya login, взема `uid` и връща устройствата като JSON.

## Windows ред за тест

### Вариант A: PowerShell + Git + Node.js

1. Инсталирай Node.js 20 LTS.
2. Инсталирай Git for Windows.
3. Отвори PowerShell.
4. Изпълни:

```powershell
git clone <REPO_URL>
cd MoniK
npm install
copy .env.example .env
notepad .env
npm start
```

5. В Notepad попълни `MONIK_TUYA_ACCESS_ID`, `MONIK_TUYA_ACCESS_SECRET`, `TUYA_DATA_CENTER`, `TUYA_COUNTRY_CODE` и `TUYA_SCHEMA` само ако тестваш локално standalone server.
6. Отвори <http://localhost:4173>.
7. В страницата въведи само съществуващ Tuya user акаунт и парола.

### Вариант B: ZIP от repo-то

Може и без Git:

1. Отвори repo-то в browser.
2. Натисни `Code` → `Download ZIP`.
3. Разархивирай ZIP файла.
4. Отвори PowerShell в папката `MoniK`.
5. Изпълни:

```powershell
npm install
copy .env.example .env
notepad .env
npm start
```

6. Отвори <http://localhost:4173>.

Git вариантът е по-добър, защото после обновяваш с `git pull`. ZIP вариантът е достатъчен само за бърза проба.

## Проверки

Преди реален Tuya login можеш да провериш, че страницата и server endpoint-ите работят:

```bash
npm run check
npm run test:page
npm audit --omit=dev
```

Очаквано: `npm run test:page` трябва да завърши с:

```text
OK: test page works at http://127.0.0.1:4173
```

## API

### `POST /api/tuya/link`

Крайният потребител подава само тези login данни:

```json
{
  "username": "name@example.com",
  "password": "tuya-password",
  "countryCode": "49",
  "schema": "tuyaSmart"
}
```

Response при успех:

```json
{
  "linked": true,
  "uid": "tuya-user-id",
  "tokenExpiresIn": 7200,
  "importedDevices": 2,
  "devices": []
}
```

## Ако не тръгне

- Ако страницата не се отваря: провери дали `npm start` още работи и дали портът е `4173`.
- Ако виждаш `MoniK Tuya connector is not configured on the server`: локалният MoniK server няма connector настройки. Това не означава, че user трябва да прави developer акаунт; означава, че server-side connector-ът не е настроен.
- Ако Tuya връща login грешка: провери data center, schema, country code и дали акаунтът е към същия Tuya app/project/region.
