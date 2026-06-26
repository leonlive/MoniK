# MoniK Tuya Link

Това е самостоятелно MoniK звено за свързване на реален Tuya акаунт и импорт на устройствата му чрез MoniK server.

## Най-бърз тест от твоя компютър

Да, трябва да свалиш кода локално, защото страницата говори с локален MoniK server (`npm start`). Не може само директно от GitHub web страницата, защото GitHub не стартира Node.js server и няма твоите Tuya secrets.

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

### 3. Настрой Tuya ключовете

Копирай `.env.example` в `.env` и попълни реалните стойности от Tuya Cloud project-а:

```bash
cp .env.example .env
```

В `.env` трябва да има:

```bash
TUYA_ACCESS_ID=your-access-id
TUYA_ACCESS_SECRET=your-access-secret
TUYA_DATA_CENTER=eu
TUYA_COUNTRY_CODE=49
TUYA_SCHEMA=tuyaSmart
PORT=4173
```

Важно:

- `TUYA_COUNTRY_CODE=49` е default за international login.
- На тест страницата има и `359 · България`, ако трябва да пробваш с България.
- `TUYA_DATA_CENTER` трябва да съвпада с Tuya Cloud project-а: `eu`, `us`, `cn`, `in`, `ea` или `we`.

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

Там въвеждаш реален Tuya username/email/телефон и Tuya парола. Формата праща `POST /api/tuya/link`, MoniK server прави Tuya login, взема `uid` и връща устройствата като JSON.

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

5. В Notepad попълни `TUYA_ACCESS_ID`, `TUYA_ACCESS_SECRET`, `TUYA_DATA_CENTER`, `TUYA_COUNTRY_CODE` и `TUYA_SCHEMA`.
6. Отвори <http://localhost:4173>.

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

Request:

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
- Ако виждаш missing `TUYA_ACCESS_ID` или `TUYA_ACCESS_SECRET`: `.env` не е попълнен или не се зарежда от shell-а.
- Ако Tuya връща login грешка: провери data center, schema, country code и дали акаунтът е към същия Tuya app/project.
