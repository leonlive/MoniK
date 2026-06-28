# MoniK Tuya SDK Bridge

Корекция: махнат е Tuya Cloud developer моделът от MoniK server-а. Няма `TUYA_ACCESS_ID`, няма `TUYA_ACCESS_SECRET`, няма `MONIK_TUYA_ACCESS_ID`, няма server-side Tuya Cloud SDK connector.

Текущият поток е за случая, който искаш: Android/iOS Tuya SDK клиентът, с вече наличния SDK/manifest/app setup, взема устройствата чрез съществуващ Tuya user акаунт и ги подава към MoniK server. MoniK server само приема и пази устройствата.

## Как работи

1. Потребителят влиза в Tuya през mobile SDK клиента.
2. Mobile SDK клиентът взема реалните устройства от Tuya акаунта.
3. Mobile SDK клиентът праща устройствата към MoniK server:

```http
POST /api/monik/devices/import
```

4. MoniK server връща колко устройства са импортирани и ги държи за проверка през:

```http
GET /api/monik/devices
```





## Хибриден тест през компютър + телефон

Това е най-бързият тест за login проблема:

1. Свържи телефона с USB.
2. Разреши USB debugging.
3. Стартирай MoniK server: `npm start`.
4. В browser отвори `http://localhost:4173`.
5. Натисни **Изчисти logcat**.
6. На телефона натисни MoniK login/import бутона.
7. В browser натисни **Прочети login log**.

Същото може и директно от PowerShell:

```powershell
npm run log:windows
```

Script-ът прави `adb devices`, `adb logcat -c`, чака да натиснеш login на телефона, после записва `monik-login.log` и филтрира важните редове.

## MoniK server token request с key файлове

Да: ако тези файлове са достъпът до MoniK server-а, `.env` трябва да сочи имената/пътищата им, а програмата трябва да ги прочете при заявката. Добавен е endpoint:

```http
POST /api/monik/token/request
```

Конфигурация:

```bash
MONIK_SERVER_TOKEN_URL=https://your-monik-server.example/api/token
MONIK_TUYA_ACCESS_ID=monik_strato_ed25519
MONIK_TUYA_PRIVATE_KEY_PATH=/opt/monik-yandex/secure/keys/monik_strato_ed25519
MONIK_TUYA_PUBLIC_KEY_PATH=/opt/monik-yandex/secure/keys/monik_strato_ed25519.pub
```

Важно: `.env` пази само имена/пътища. Самите ключове не се commit-ват. При заявка server-ът чете private/public key файловете, подписва payload-а и го изпраща към `MONIK_SERVER_TOKEN_URL`. Ако `MONIK_SERVER_TOKEN_URL` не е зададен, endpoint-ът връща signed request обекта без да го изпраща.

## Как е вързано с телефона?

Не чрез pairing и не като отделено приложение. Този Node server вече работи като ADB bridge към инсталирания MoniK app на телефона.

1. Телефонът е вързан с USB към компютъра.
2. USB debugging е разрешен.
3. MoniK Android app е инсталиран и прави Tuya SDK login вътре в приложението.
4. MoniK app записва devices export JSON в app storage, например `files/monik_tuya_devices.json`.
5. Node server изпълнява:

```bash
adb shell run-as com.monik.app cat files/monik_tuya_devices.json
```

6. Прочетеният JSON се импортва в MoniK server.

Endpoint за автоматично ADB взимане:

```http
POST /api/monik/adb/import
```

Body:

```json
{
  "packageName": "com.monik.app",
  "deviceFile": "files/monik_tuya_devices.json"
}
```

ADB статус:

```http
GET /api/monik/adb/status
```

Конфигурация през env, ако package/file са различни:

```bash
MONIK_ANDROID_PACKAGE=com.monik.app
MONIK_TUYA_EXPORT_FILE=files/monik_tuya_devices.json
```

## Къде се въвеждат email и парола?

Не в тази browser страница. Email/парола трябва да се въвеждат в MoniK Android/iOS приложението, където е Tuya mobile SDK и manifest setup-ът.

Този Node server е само приемник:

1. MoniK app показва Tuya login screen.
2. Tuya mobile SDK връща homes/devices в app-а.
3. App-ът праща реалните устройства към `POST /api/monik/devices/import`.
4. Тази browser страница е само тестов начин ръчно да симулираш стъпка 3 с JSON payload.

Файлове като private key/public key, `.pem`, `.key`, `.pub`, `.jks`, `.keystore` не се ползват от този Node server и не трябва да се commit-ват. Добавени са в `.gitignore`.

## Локален тест на server-а

```bash
npm install
npm start
```

Отвори:

```text
http://localhost:4173
```

Тест страницата не прави fake Tuya login и не иска developer credentials. Тя служи да подадеш JSON payload, какъвто Android SDK клиентът трябва да изпрати към MoniK.


## Автоматичен Windows старт

За да не натискаш стъпките една по една, добавен е PowerShell script:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-monik-windows.ps1
```

Той автоматично:

1. проверява `node -v` и `npm -v`;
2. пуска `npm install`;
3. пуска `npm run check`;
4. пуска `npm run test:page`;
5. отваря `http://localhost:4173`;
6. стартира server-а с `npm start`.

Ако repo-то вече е git clone и искаш script-ът да опита update преди старта:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-monik-windows.ps1 -Update
```

Ако GitHub Desktop/Git показва local inconsistencies и **нямаш локални промени за пазене**, може да пуснеш автоматично чистене + update:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-monik-windows.ps1 -Update -ResetLocalChanges
```

Внимание: `-ResetLocalChanges` изпълнява `git reset --hard` и `git clean -fd`, т.е. трие локални неприбрани промени.

## Windows ред

```powershell
git clone <REPO_URL>
cd MoniK
npm install
npm start
```

Или ZIP:

```powershell
npm install
npm start
```

После отвори <http://localhost:4173>.

## API

### `POST /api/monik/devices/import`

Request от mobile SDK клиента:

```json
{
  "devices": [
    {
      "devId": "real-device-id",
      "name": "Lamp",
      "productId": "product-id",
      "category": "dj",
      "online": true
    }
  ]
}
```

Response:

```json
{
  "imported": true,
  "importedDevices": 1,
  "lastImport": "2026-06-26T00:00:00.000Z",
  "devices": []
}
```

### `GET /api/monik/devices`

Връща последно импортираните устройства.


## Ако виждаш `Cannot find package @tuya/tuya-connector-nodejs`

Това означава, че на компютъра ти още се стартира стара версия на `src/server.js`, която import-ва стария cloud connector `src/tuyaClient.js`. В последната версия server-ът вече не използва този пакет.

Направи едно от двете:

```powershell
git pull
npm install
npm start
```

или, ако си със ZIP, изтрий старата папка `MoniK`, свали ZIP наново и пусни:

```powershell
npm install
npm start
```

Добавен е и compatibility `src/tuyaClient.js` файл без външни зависимости, за да не пада Node с `ERR_MODULE_NOT_FOUND`, ако някъде остане стар import.

## Проверки

```bash
npm run check
npm run test:page
npm audit --omit=dev
```

Очаквано:

```text
OK: SDK bridge works at http://127.0.0.1:4173
```
