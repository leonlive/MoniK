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
