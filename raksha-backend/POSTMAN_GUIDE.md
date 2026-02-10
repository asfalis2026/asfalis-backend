# Raksha Backend - Postman Testing Guide

This guide helps you set up Postman to test the Raksha Backend API efficiently.

## 1. Create an Environment

Using an environment allows you to switch between Local, Staging, and Production easily without changing request URLs.

1. Open Postman and go to **Distributions** (or **Environments** based on your version).
2. Click **Create Environment** (limit to "Local").
3. Add the following variables:

| Variable | Initial Value | Current Value |
| :--- | :--- | :--- |
| `baseUrl` | `http://localhost:5000/api` | `http://localhost:5000/api` |
| `token` | *(leave empty)* | *(leave empty)* |

4. **Save** the environment and select it from the top-right dropdown.

---

## 2. Set Up Collection

Create a new Collection named **"Raksha Backend"**.

### Authorization (Collection Level)
To avoid adding headers to every request, set up auth at the collection level:

1. Click on the **Raksha Backend** collection.
2. Go to the **Authorization** tab.
3. Select Type: **Bearer Token**.
4. Set Token: `{{token}}`.
5. Save.

Now, every request in this collection will automatically use the token variable!

---

## 3. Create Requests

Organize your requests into folders.

### Folder: Auth

**1. Register (Email)**
- **Method**: `POST`
- **URL**: `{{baseUrl}}/auth/register/email`
- **Body** (JSON):
  ```json
  {
      "email": "test@example.com",
      "password": "password123",
      "full_name": "Test User"
  }
  ```
- **Tests** (Tab): Add this script to auto-save the token:
  ```javascript
  var jsonData = pm.response.json();
  if (jsonData.success && jsonData.data.access_token) {
      pm.environment.set("token", jsonData.data.access_token);
      console.log("Token saved!");
  }
  ```

**2. Login (Email)**
- **Method**: `POST`
- **URL**: `{{baseUrl}}/auth/login/email`
- **Body** (JSON):
  ```json
  {
      "email": "test@example.com",
      "password": "password123"
  }
  ```
- **Tests**: Use the same script as above.

### Folder: User

**1. Get Profile**
- **Method**: `GET`
- **URL**: `{{baseUrl}}/user/profile`

Current Response:
{
    "msg": "Missing Authorization Header"
}

**2. Update Profile**
- **Method**: `PUT`
- **URL**: `{{baseUrl}}/user/profile`
- **Body** (JSON):
  ```json
  {
      "full_name": "Updated Name",
      "phone": "+1234567890"
  }
  ```

Current Response:
{
    "msg": "Missing Authorization Header"
}

### Folder: SOS

**1. Trigger SOS**
- **Method**: `POST`
- **URL**: `{{baseUrl}}/sos/trigger`
- **Body** (JSON):
  ```json
  {
      "latitude": 28.7041,
      "longitude": 77.1025,
      "trigger_type": "manual"
  }
  ```

### Folder: Contacts

**1. Add Contact**
- **Method**: `POST`
- **URL**: `{{baseUrl}}/contacts`
- **Body** (JSON):
  ```json
  {
      "name": "Mom",
      "phone": "+919876543210",
      "relationship": "Parent",
      "is_primary": true
  }
  ```

---

## 4. Run the Tests

1. Select your **Local** environment.
2. Send the **Register** request first.
   - Check the "Tests" tab output: You should see "Token saved!".
3. Try **Get Profile**.
   - It should return `200 OK` with your user details.
4. Try **Trigger SOS**.
   - It should return `201 Created`.

## 5. Troubleshooting "Missing Authorization Header"

If you see `{"msg": "Missing Authorization Header"}`, follow these steps:

1. **Check Variable**: Hover over `{{token}}` in the **Authorization** tab.
   - If it says `Unresolved Variable`, the token isn't saved.
   - **Fix**: Run the **Login** request again and check the **Tests** tab output for "Token saved!".

2. **Check Environment**: Ensure "Local" is selected in the top-right dropdown, not "No Environment".

3. **Check Request Auth**: Click on the specific request (e.g., Get Profile) -> **Authorization** tab.
   - Ensure "Type" is set to **Inherit auth from parent**.
   - If it's set to "No Auth", change it to Inherit.

4. **Manual Token**: Copy the `access_token` from the Login response and manually paste it into the **Authorization** tab (Type: Bearer Token) of the request to verify it works.

If you get `401 Unauthorized`, make sure you ran the Register/Login request first and that the `token` variable in your environment is populated.
