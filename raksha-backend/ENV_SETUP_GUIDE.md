# Environment Variable Setup Guide for RAKSHA Backend

## 1. Random Secrets (SECRET_KEY, JWT_SECRET_KEY)
You can generate secure random strings using Python or OpenSSL. Run this command in your terminal:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Use the output for both `SECRET_KEY` and `JWT_SECRET_KEY` (generate two different strings).

## 2. Google Maps API (GOOGLE_MAPS_API_KEY)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., "raksha-backend").
3. Navigate to **APIs & Services > Library**.
4. Enable the **Maps JavaScript API** and **Geocoding API**.
5. Navigate to **APIs & Services > Credentials**.
6. Click **Create Credentials > API Key**.
7. Copy the key and paste it into `.env`.

## 3. Firebase Cloud Messaging (FIREBASE_CREDENTIALS_PATH)
1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Create a new project.
3. Click the gear icon > **Project settings**.
4. Go to the **Service accounts** tab.
5. Click **Generate new private key**.
6. Save the downloaded JSON file as `firebase-service-account.json` in the `raksha-backend/` root directory.
7. Ensure `.env` points to this file: `FIREBASE_CREDENTIALS_PATH=./firebase-service-account.json`.

<!-- import firebase_admin
from firebase_admin import credentials

cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred) -->


## 4. Twilio SMS (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)
1. Sign up for a free account at [Twilio](https://www.twilio.com/).
2. Verify your phone number.
3. Go to the Console Dashboard.
4. Copy the **Account SID** and **Auth Token**.
5. Click **Get a Trial Number** if you don't have one, and copy that number.
6. Paste these values into `.env`.

## 5. Email Service (MAIL_USERNAME, MAIL_PASSWORD)
If using Gmail:
1. Go to your Google Account > Security.
2. Enable **2-Step Verification**.
3. Search for **App Passwords**.
4. Create a new app password (name it "Raksha Backend").
5. Copy the 16-character password and use it as `MAIL_PASSWORD`.
6. Use your Gmail address as `MAIL_USERNAME`.

## 6. Redis (REDIS_URL, CELERY_BROKER_URL)
If running via Docker Compose (`docker-compose up`), Redis is automatically configured.
If running locally without Docker:
1. Install Redis (`brew install redis` on Mac).
2. Start Redis (`redis-server`).
3. The default URL `redis://localhost:6379/0` should verify.
