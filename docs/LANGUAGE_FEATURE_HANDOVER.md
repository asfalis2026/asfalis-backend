# Frontend Handover Document - Language Preference Feature

**Date:** 2026-06-12
**Version:** 2.2.0

---

## Overview

A new language preference feature has been added to the backend. Users can now select their preferred language (English, Hindi, or Bengali) in the app settings. The backend stores this preference and returns it in API responses so the frontend can display translated content.

---

## 🌍 Language Feature

### Supported Languages

| Code | Language | Display Name |
|------|----------|--------------|
| `en` | English | English |
| `hin` | Hindi | हिंदी |
| `ben` | Bengali | বাংলা |

### Database Changes

- **Table:** `user_settings`
- **Column:** `language`
- **Type:** ENUM (`'en'`, `'hin'`, `'ben'`)
- **Default:** `'en'` (English)
- **Nullable:** No

---

## 📱 API Integration

### Get User Settings

**Endpoint:** `GET /settings`

**Response:**
```json
{
  "success": true,
  "data": {
    "emergency_number": "911",
    "sos_message": "Emergency! I need help...",
    "shake_sensitivity": "medium",
    "battery_optimization": true,
    "haptic_feedback": true,
    "auto_sos_enabled": false,
    "language": "en"
  }
}
```

---

### Update User Settings (Change Language)

**Endpoint:** `PUT /settings`

**Request Body:**
```json
{
  "language": "hin"
}
```

**Valid values:** `"en"`, `"hin"`, `"ben"`

**Success Response:**
```json
{
  "success": true,
  "data": {
    "emergency_number": "911",
    "sos_message": "Emergency! I need help...",
    "shake_sensitivity": "medium",
    "battery_optimization": true,
    "haptic_feedback": true,
    "auto_sos_enabled": false,
    "language": "hin"
  }
}
```

**Error Response (Invalid language):**
```json
{
  "detail": "Validation error"
}
```

---

## 🔧 Frontend Implementation Guide

### 1. Language Picker UI

Add a language selector in the app settings screen. Recommended implementation:

```kotlin
// Example: Language options
val languageOptions = listOf(
    LanguageOption("en", "English"),
    LanguageOption("hin", "हिंदी"),
    LanguageOption("ben", "বাংলা")
)

// Selected value from settings
var selectedLanguage by remember { mutableStateOf("en") }
```

### 2. Fetch Current Language

On settings screen load, call `GET /settings` and extract the `language` field:

```kotlin
// After getting settings response
val currentLanguage = settingsResponse.data.language  // "en" | "hin" | "ben"
selectedLanguage = currentLanguage
```

### 3. Save Language Preference

When user selects a new language, call `PUT /settings`:

```kotlin
fun updateLanguage(languageCode: String) {
    val request = SettingsUpdateRequest(language = languageCode)
    api.updateSettings(request).onSuccess {
        selectedLanguage = languageCode
        // Update local storage for offline access
        localStorage.save("app_language", languageCode)
        // Reload UI with new language
        applyLanguage(languageCode)
    }
}
```

### 4. Store Language Locally

Save the language preference locally for immediate use before API call:

```kotlin
// Save to DataStore / SharedPreferences
fun saveLanguagePreference(languageCode: String) {
    preferences.edit().putString("language", languageCode).apply()
}

// Load on app start
fun loadLanguagePreference(): String {
    return preferences.getString("language", "en") ?: "en"
}
```

### 5. Apply Language to UI

Use the stored language preference to display translated text:

```kotlin
// Load translations based on language
fun applyLanguage(languageCode: String) {
    val translations = when (languageCode) {
        "hin" -> HindiTranslations
        "ben" -> BengaliTranslations
        else -> EnglishTranslations
    }
    // Update UI strings
}
```

---

## 📋 Translations Required

The frontend needs translations for the following strings. Below is the initial mapping:

### English (en) - Default
```
settings_title = "Settings"
language_label = "Language"
language_english = "English"
language_hindi = "Hindi"
language_bengali = "Bengali"
sos_settings = "SOS Settings"
emergency_number = "Emergency Number"
shake_sensitivity = "Shake Sensitivity"
battery_optimization = "Battery Optimization"
haptic_feedback = "Haptic Feedback"
auto_sos = "Auto SOS"
save = "Save"
cancel = "Cancel"
```

### Hindi (hin)
```
settings_title = "सेटिंग्स"
language_label = "भाषा"
language_english = "अंग्रेज़ी"
language_hindi = "हिंदी"
language_bengali = "बंगाली"
sos_settings = "SOS सेटिंग्स"
emergency_number = "आपातकालीन नंबर"
shake_sensitivity = "शेक संवेदनशीलता"
battery_optimization = "बैटरी ऑप्टिमाइजेशन"
haptic_feedback = "हैप्टिक फीडबैक"
auto_sos = "ऑटो SOS"
save = "सहेजें"
cancel = "रद्द करें"
```

### Bengali (ben)
```
settings_title = "সেটিংস"
language_label = "ভাষা"
language_english = "ইংরেজি"
language_hindi = "হিন্দি"
language_bengali = "বাংলা"
sos_settings = "SOS সেটিংস"
emergency_number = "জরুরি নম্বর"
shake_sensitivity = "শেক সংবেদনশীলতা"
battery_optimization = "ব্যাটারি অপ্টিমাইজেশন"
haptic_feedback = "হ্যাপটিক ফিডব্যাক"
auto_sos = "অটো SOS"
save = "সংরক্ষণ"
cancel = "বাতিল"
```

---

## 🔄 User Flow

1. **App Launch** → Load saved language from local storage (default: `"en"`)
2. **Settings Screen** → Call `GET /settings` → Get current `language` value
3. **User Changes Language** → Call `PUT /settings` with new `language`
4. **Success** → Update local storage → Apply translations to UI
5. **Next Launch** → Use saved language preference

---

## ⚠️ Important Notes

1. **Default Value:** New users will have `language: "en"` by default
2. **Existing Users:** After migration, existing users will have `language: "en"` (default)
3. **Offline Support:** Store language preference locally to work offline
4. **API Failure:** If API fails, fall back to locally saved preference

---

## 🧪 Testing Checklist

- [ ] Test fetching settings and verify `language` field is returned
- [ ] Test updating language to `"hin"` and verify it saves
- [ ] Test updating language to `"ben"` and verify it saves
- [ ] Test updating language back to `"en"` and verify it saves
- [ ] Verify language persists after app restart
- [ ] Verify UI displays correct translations for each language
- [ ] Test error handling for invalid language values

---

## 📞 Questions?

If you have any questions about these changes, contact the backend team.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-12 | Initial document - Language preference feature v2.2.0 |
