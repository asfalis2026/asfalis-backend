# 🔌 RAKSHA — Flask API Integration Guide for Android (Jetpack Compose)

> **Step-by-step guide** to connect the RAKSHA Women Safety Android frontend with the Flask backend.  
> Covers Retrofit setup, dependency injection, repository pattern, JWT auth, WebSocket, and per-screen integration code.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Android Dependencies](#2-android-dependencies)
3. [Gradle Configuration](#3-gradle-configuration)
4. [Network Layer Setup](#4-network-layer-setup)
5. [JWT Token Management](#5-jwt-token-management)
6. [API Service Interfaces](#6-api-service-interfaces)
7. [Data Models (DTOs)](#7-data-models-dtos)
8. [Repository Layer](#8-repository-layer)
9. [ViewModels](#9-viewmodels)
10. [Screen-by-Screen Integration](#10-screen-by-screen-integration)
11. [WebSocket Integration (Live Location)](#11-websocket-integration-live-location)
12. [Firebase Cloud Messaging Setup](#12-firebase-cloud-messaging-setup)
13. [Error Handling on Android](#13-error-handling-on-android)
14. [Offline Support & Caching](#14-offline-support--caching)
15. [Testing the Connection](#15-testing-the-connection)
16. [Flask Backend Checklist](#16-flask-backend-checklist)

---

## 1. Architecture Overview

### Current State (No Backend)

```
┌──────────────────────┐
│   Jetpack Compose UI │
│   (Screens)          │
│        │             │
│   SharedPreferences  │  ← All data is local/hardcoded
│   (raksha_prefs)     │
└──────────────────────┘
```

### Target State (With Flask Backend)

```
┌───────────────────────���──────────────────────────────┐
│                    Android App                        │
│                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐  │
│  │  Compose   │───▶│  ViewModel │───▶│ Repository  │  │
│  │  Screens   │◀───│            │◀───│            │  │
│  └────────────┘    └────────────┘    └─────┬──────┘  │
│                                            │         │
│                    ┌───────────────────────┬┘         │
│                    │                       │          │
│             ┌──────▼──────┐     ┌─────────▼────────┐ │
│             │  Retrofit   │     │  TokenManager    │ │
│             │  (REST API) │     │  (DataStore)     │ │
│             └──────┬──────┘     └──────────────────┘ │
│                    │                                  │
│             ┌──────▼──────┐                           │
│             │  OkHttp +   │                           │
│             │  Auth       │                           │
│             │  Interceptor│                           │
│             └──────┬──────┘                           │
└────────────────────┼─────────────────────────────────┘
                     │  HTTPS
                     ▼
┌──────────────────────────────────────────────────────┐
│               Flask Backend Server                    │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  Routes  │  │ Services │  │  PostgreSQL DB   │   │
│  │  (API)   │──│  (Logic) │──│  + Redis Cache   │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────┘
```

---

## 2. Android Dependencies

Add these dependencies to your **module-level** `build.gradle.kts` (i.e., `app/build.gradle.kts`):

```kotlin
// app/build.gradle.kts

dependencies {
    // === EXISTING DEPENDENCIES (keep all your current ones) ===

    // === NEW: NETWORKING ===
    // Retrofit — HTTP client for REST APIs
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")

    // OkHttp — HTTP engine + logging
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Gson — JSON serialization/deserialization
    implementation("com.google.code.gson:gson:2.11.0")

    // === NEW: LOCAL STORAGE (replaces SharedPreferences for tokens) ===
    // DataStore — modern key-value storage
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    // === NEW: VIEWMODEL + LIFECYCLE ===
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    // === NEW: COROUTINES (likely already present) ===
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // === NEW: WEBSOCKET (for live location) ===
    // Socket.IO client for Android
    implementation("io.socket:socket.io-client:2.1.1")

    // === NEW: FIREBASE CLOUD MESSAGING ===
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-messaging-ktx")

    // === NEW: GOOGLE MAPS (for LiveMapScreen) ===
    implementation("com.google.maps.android:maps-compose:6.2.1")
    implementation("com.google.android.gms:play-services-maps:19.0.0")
    implementation("com.google.android.gms:play-services-location:21.3.0")

    // === OPTIONAL: Dependency Injection ===
    // Hilt (recommended for cleaner architecture)
    implementation("com.google.dagger:hilt-android:2.52")
    kapt("com.google.dagger:hilt-android-compiler:2.52")
    implementation("androidx.hilt:hilt-navigation-compose:1.2.0")
}
```

> **Note:** If you use Hilt, also add the Hilt plugin in your project-level `build.gradle.kts`:
> ```kotlin
> plugins {
>     id("com.google.dagger.hilt.android") version "2.52" apply false
> }
> ```

---

## 3. Gradle Configuration

### Add Internet Permissions

Add these to `app/src/main/AndroidManifest.xml` (some may already exist from the permissions screen):

```xml
<!-- AndroidManifest.xml -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Network -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <!-- Location (likely already present) -->
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION" />

    <!-- SMS (likely already present) -->
    <uses-permission android:name="android.permission.SEND_SMS" />

    <!-- Foreground Service (for background location tracking) -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" />

    <application
        ...
        android:usesCleartextTraffic="true"> <!-- Only for local dev (http://10.0.2.2) -->
        ...
    </application>
</manifest>
```

### Network Security Config (for local development)

Create `app/src/main/res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Allow cleartext for local development only -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">10.0.2.2</domain>  <!-- Android emulator localhost -->
        <domain includeSubdomains="true">192.168.1.0</domain> <!-- Your local IP -->
    </domain-config>
</network-security-config>
```

Reference it in `AndroidManifest.xml`:

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ... >
```

---

## 4. Network Layer Setup

### 4.1 API Constants

Create a new package: `com.yourname.womensafety.data.network`

```kotlin
// data/network/ApiConstants.kt
package com.yourname.womensafety.data.network

object ApiConstants {
    // Change this based on your environment
    // Emulator → 10.0.2.2 (maps to host machine's localhost)
    // Physical device → your machine's local IP (e.g., 192.168.1.100)
    // Production → your deployed server URL

    const val BASE_URL_LOCAL = "http://10.0.2.2:5000/api/"
    const val BASE_URL_PRODUCTION = "https://your-server.com/api/"

    // Toggle this for dev vs prod
    const val BASE_URL = BASE_URL_LOCAL

    // WebSocket
    const val WS_URL_LOCAL = "http://10.0.2.2:5000"
    const val WS_URL_PRODUCTION = "https://your-server.com"
    const val WS_URL = WS_URL_LOCAL
}
```

### 4.2 Auth Interceptor (Automatic JWT Injection)

```kotlin
// data/network/AuthInterceptor.kt
package com.yourname.womensafety.data.network

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(
    private val tokenManager: TokenManager
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()

        // Skip auth for public endpoints
        val publicPaths = listOf(
            "auth/login", "auth/register", "auth/send-otp",
            "auth/verify-otp", "auth/resend-otp", "auth/forgot-password",
            "auth/google", "auth/refresh"
        )

        val isPublic = publicPaths.any { originalRequest.url.encodedPath.contains(it) }
        if (isPublic) {
            return chain.proceed(originalRequest)
        }

        // Get token from DataStore
        val token = runBlocking { tokenManager.getAccessToken().first() }

        val authenticatedRequest = if (token != null) {
            originalRequest.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            originalRequest
        }

        val response = chain.proceed(authenticatedRequest)

        // If 401, try to refresh the token
        if (response.code == 401) {
            response.close()
            val newToken = runBlocking { refreshToken(tokenManager) }
            if (newToken != null) {
                val retryRequest = originalRequest.newBuilder()
                    .header("Authorization", "Bearer $newToken")
                    .build()
                return chain.proceed(retryRequest)
            }
        }

        return response
    }

    private suspend fun refreshToken(tokenManager: TokenManager): String? {
        val refreshToken = tokenManager.getRefreshToken().first() ?: return null

        // Make a synchronous call to refresh endpoint
        // In production, use a separate OkHttp client without this interceptor
        // to avoid infinite loops
        return try {
            // This is simplified — see Section 5 for full implementation
            val newAccessToken = tokenManager.refreshAccessToken(refreshToken)
            newAccessToken
        } catch (e: Exception) {
            tokenManager.clearTokens()
            null
        }
    }
}
```

### 4.3 Retrofit Client (Singleton)

```kotlin
// data/network/RetrofitClient.kt
package com.yourname.womensafety.data.network

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private var retrofit: Retrofit? = null

    fun getInstance(tokenManager: TokenManager): Retrofit {
        if (retrofit == null) {
            val loggingInterceptor = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY // Use NONE in production
            }

            val okHttpClient = OkHttpClient.Builder()
                .addInterceptor(AuthInterceptor(tokenManager))
                .addInterceptor(loggingInterceptor)
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build()

            retrofit = Retrofit.Builder()
                .baseUrl(ApiConstants.BASE_URL)
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
        }
        return retrofit!!
    }

    // Get a specific API service
    inline fun <reified T> createService(tokenManager: TokenManager): T {
        return getInstance(tokenManager).create(T::class.java)
    }
}
```

---

## 5. JWT Token Management

Replace the current `SharedPreferences` (`raksha_prefs`) approach with **DataStore** for secure token storage.

### 5.1 Token Manager

```kotlin
// data/local/TokenManager.kt
package com.yourname.womensafety.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

// Extension property for DataStore
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "raksha_auth")

class TokenManager(private val context: Context) {

    companion object {
        private val ACCESS_TOKEN = stringPreferencesKey("access_token")
        private val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
        private val USER_ID = stringPreferencesKey("user_id")
        private val IS_LOGGED_IN = booleanPreferencesKey("is_logged_in")
        private val ONBOARDING_COMPLETE = booleanPreferencesKey("onboarding_complete")
    }

    // --- ACCESS TOKEN ---
    fun getAccessToken(): Flow<String?> = context.dataStore.data.map { it[ACCESS_TOKEN] }

    suspend fun saveAccessToken(token: String) {
        context.dataStore.edit { it[ACCESS_TOKEN] = token }
    }

    // --- REFRESH TOKEN ---
    fun getRefreshToken(): Flow<String?> = context.dataStore.data.map { it[REFRESH_TOKEN] }

    suspend fun saveRefreshToken(token: String) {
        context.dataStore.edit { it[REFRESH_TOKEN] = token }
    }

    // --- SAVE BOTH TOKENS (after login) ---
    suspend fun saveTokens(accessToken: String, refreshToken: String, userId: String) {
        context.dataStore.edit { prefs ->
            prefs[ACCESS_TOKEN] = accessToken
            prefs[REFRESH_TOKEN] = refreshToken
            prefs[USER_ID] = userId
            prefs[IS_LOGGED_IN] = true
        }
    }

    // --- LOGIN STATE ---
    fun isLoggedIn(): Flow<Boolean> = context.dataStore.data.map { it[IS_LOGGED_IN] ?: false }

    fun getUserId(): Flow<String?> = context.dataStore.data.map { it[USER_ID] }

    // --- ONBOARDING STATE (migrated from SharedPreferences) ---
    fun isOnboardingComplete(): Flow<Boolean> =
        context.dataStore.data.map { it[ONBOARDING_COMPLETE] ?: false }

    suspend fun setOnboardingComplete() {
        context.dataStore.edit { it[ONBOARDING_COMPLETE] = true }
    }

    // --- LOGOUT ---
    suspend fun clearTokens() {
        context.dataStore.edit { prefs ->
            prefs.remove(ACCESS_TOKEN)
            prefs.remove(REFRESH_TOKEN)
            prefs.remove(USER_ID)
            prefs[IS_LOGGED_IN] = false
        }
    }

    // --- REFRESH ACCESS TOKEN ---
    suspend fun refreshAccessToken(refreshToken: String): String? {
        // This will be called by AuthInterceptor
        // Use a separate Retrofit instance WITHOUT AuthInterceptor to avoid loops
        return try {
            val refreshService = RetrofitClient.createRefreshService()
            val response = refreshService.refreshToken(RefreshRequest(refreshToken))
            if (response.isSuccessful && response.body()?.success == true) {
                val newToken = response.body()!!.data.accessToken
                saveAccessToken(newToken)
                newToken
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }
}
```

### 5.2 Migrating from SharedPreferences

Currently, `SplashScreen.kt` uses:
```kotlin
val sharedPref = context.getSharedPreferences("raksha_prefs", Context.MODE_PRIVATE)
val isLoggedIn = sharedPref.getBoolean("is_logged_in", false)
val onboardingDone = sharedPref.getBoolean("onboarding_complete", false)
```

**Replace with:**
```kotlin
// In SplashScreen ViewModel
class SplashViewModel(private val tokenManager: TokenManager) : ViewModel() {

    val isLoggedIn = tokenManager.isLoggedIn()
    val isOnboardingComplete = tokenManager.isOnboardingComplete()

    fun validateSession() = viewModelScope.launch {
        val token = tokenManager.getAccessToken().first()
        if (token != null) {
            // Call backend to validate token
            try {
                val response = authRepository.validateToken()
                if (!response.success) {
                    tokenManager.clearTokens()
                }
            } catch (e: Exception) {
                // Token invalid or network error — stay logged in for offline support
            }
        }
    }
}
```

---

## 6. API Service Interfaces

Define Retrofit service interfaces for each backend module.

### 6.1 Auth API Service

```kotlin
// data/network/api/AuthApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface AuthApiService {

    @POST("auth/register/email")
    suspend fun registerWithEmail(
        @Body request: EmailRegisterRequest
    ): Response<ApiResponse<AuthData>>

    @POST("auth/login/email")
    suspend fun loginWithEmail(
        @Body request: EmailLoginRequest
    ): Response<ApiResponse<AuthData>>

    @POST("auth/send-otp")
    suspend fun sendOtp(
        @Body request: SendOtpRequest
    ): Response<ApiResponse<OtpData>>

    @POST("auth/verify-otp")
    suspend fun verifyOtp(
        @Body request: VerifyOtpRequest
    ): Response<ApiResponse<AuthData>>

    @POST("auth/resend-otp")
    suspend fun resendOtp(
        @Body request: SendOtpRequest
    ): Response<ApiResponse<OtpData>>

    @POST("auth/refresh")
    suspend fun refreshToken(
        @Body request: RefreshRequest
    ): Response<ApiResponse<RefreshData>>

    @POST("auth/logout")
    suspend fun logout(): Response<ApiResponse<Unit>>

    @GET("auth/validate")
    suspend fun validateToken(): Response<ApiResponse<ValidateData>>

    @POST("auth/forgot-password")
    suspend fun forgotPassword(
        @Body request: ForgotPasswordRequest
    ): Response<ApiResponse<Unit>>

    @POST("auth/google")
    suspend fun googleSignIn(
        @Body request: GoogleSignInRequest
    ): Response<ApiResponse<AuthData>>
}
```

### 6.2 User API Service

```kotlin
// data/network/api/UserApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface UserApiService {

    @GET("user/profile")
    suspend fun getProfile(): Response<ApiResponse<UserProfile>>

    @PUT("user/profile")
    suspend fun updateProfile(
        @Body request: UpdateProfileRequest
    ): Response<ApiResponse<UserProfile>>

    @PUT("user/fcm-token")
    suspend fun updateFcmToken(
        @Body request: FcmTokenRequest
    ): Response<ApiResponse<Unit>>

    @DELETE("user/account")
    suspend fun deleteAccount(): Response<ApiResponse<Unit>>
}
```

### 6.3 Contacts API Service

```kotlin
// data/network/api/ContactsApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface ContactsApiService {

    @GET("contacts")
    suspend fun getContacts(): Response<ApiResponse<List<TrustedContact>>>

    @POST("contacts")
    suspend fun addContact(
        @Body request: AddContactRequest
    ): Response<ApiResponse<TrustedContact>>

    @PUT("contacts/{id}")
    suspend fun updateContact(
        @Path("id") contactId: String,
        @Body request: UpdateContactRequest
    ): Response<ApiResponse<TrustedContact>>

    @DELETE("contacts/{id}")
    suspend fun deleteContact(
        @Path("id") contactId: String
    ): Response<ApiResponse<Unit>>

    @PUT("contacts/{id}/primary")
    suspend fun setPrimaryContact(
        @Path("id") contactId: String
    ): Response<ApiResponse<TrustedContact>>
}
```

### 6.4 SOS API Service

```kotlin
// data/network/api/SosApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface SosApiService {

    @POST("sos/trigger")
    suspend fun triggerSos(
        @Body request: SosTriggerRequest
    ): Response<ApiResponse<SosAlertData>>

    @POST("sos/send-now")
    suspend fun sendSosNow(
        @Body request: SosSendNowRequest
    ): Response<ApiResponse<SosAlertData>>

    @POST("sos/cancel")
    suspend fun cancelSos(
        @Body request: SosCancelRequest
    ): Response<ApiResponse<Unit>>

    @GET("sos/history")
    suspend fun getSosHistory(): Response<ApiResponse<List<SosHistoryItem>>>
}
```

### 6.5 Location API Service

```kotlin
// data/network/api/LocationApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface LocationApiService {

    @POST("location/update")
    suspend fun updateLocation(
        @Body request: LocationUpdateRequest
    ): Response<ApiResponse<Unit>>

    @GET("location/current")
    suspend fun getCurrentLocation(): Response<ApiResponse<LocationData>>

    @POST("location/share/start")
    suspend fun startSharing(): Response<ApiResponse<SharingData>>

    @POST("location/share/stop")
    suspend fun stopSharing(): Response<ApiResponse<Unit>>
}
```

### 6.6 Settings API Service

```kotlin
// data/network/api/SettingsApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface SettingsApiService {

    @GET("settings")
    suspend fun getSettings(): Response<ApiResponse<UserSettings>>

    @PUT("settings")
    suspend fun updateSettings(
        @Body request: UpdateSettingsRequest
    ): Response<ApiResponse<UserSettings>>
}
```

### 6.7 Device API Service

```kotlin
// data/network/api/DeviceApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface DeviceApiService {

    @POST("device/register")
    suspend fun registerDevice(
        @Body request: RegisterDeviceRequest
    ): Response<ApiResponse<DeviceData>>

    @GET("device/status")
    suspend fun getDeviceStatus(): Response<ApiResponse<DeviceData>>

    @PUT("device/{id}/status")
    suspend fun updateDeviceStatus(
        @Path("id") deviceId: String,
        @Body request: UpdateDeviceStatusRequest
    ): Response<ApiResponse<DeviceData>>

    @DELETE("device/{id}")
    suspend fun removeDevice(
        @Path("id") deviceId: String
    ): Response<ApiResponse<Unit>>
}
```

### 6.8 Support API Service

```kotlin
// data/network/api/SupportApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface SupportApiService {

    @GET("support/faq")
    suspend fun getFaqs(
        @Query("search") search: String? = null
    ): Response<ApiResponse<List<FaqItem>>>

    @POST("support/ticket")
    suspend fun createTicket(
        @Body request: CreateTicketRequest
    ): Response<ApiResponse<TicketData>>

    @GET("support/tickets")
    suspend fun getTickets(): Response<ApiResponse<List<TicketData>>>
}
```

### 6.9 Protection API Service

```kotlin
// data/network/api/ProtectionApiService.kt
package com.yourname.womensafety.data.network.api

import com.yourname.womensafety.data.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface ProtectionApiService {

    @POST("protection/toggle")
    suspend fun toggleProtection(
        @Body request: ToggleProtectionRequest
    ): Response<ApiResponse<ProtectionStatus>>

    @POST("protection/sensor-data")
    suspend fun sendSensorData(
        @Body request: SensorDataRequest
    ): Response<ApiResponse<SensorAnalysisResult>>

    @GET("protection/status")
    suspend fun getProtectionStatus(): Response<ApiResponse<ProtectionStatus>>
}
```

---

## 7. Data Models (DTOs)

### 7.1 Generic API Response Wrapper

```kotlin
// data/network/dto/ApiResponse.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Generic wrapper matching the Flask backend response format:
 * { "success": true, "data": {...}, "message": "..." }
 */
data class ApiResponse<T>(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: T,
    @SerializedName("message") val message: String? = null,
    @SerializedName("error") val error: ApiError? = null
)

data class ApiError(
    @SerializedName("code") val code: String,
    @SerializedName("message") val message: String,
    @SerializedName("details") val details: Map<String, String>? = null
)
```

### 7.2 Auth DTOs

```kotlin
// data/network/dto/AuthDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

// --- Requests ---
data class EmailRegisterRequest(
    @SerializedName("full_name") val fullName: String,
    @SerializedName("email") val email: String,
    @SerializedName("password") val password: String
)

data class EmailLoginRequest(
    @SerializedName("email") val email: String,
    @SerializedName("password") val password: String
)

data class SendOtpRequest(
    @SerializedName("phone") val phone: String
)

data class VerifyOtpRequest(
    @SerializedName("phone") val phone: String,
    @SerializedName("otp_code") val otpCode: String
)

data class RefreshRequest(
    @SerializedName("refresh_token") val refreshToken: String
)

data class ForgotPasswordRequest(
    @SerializedName("email") val email: String
)

data class GoogleSignInRequest(
    @SerializedName("id_token") val idToken: String
)

// --- Responses ---
data class AuthData(
    @SerializedName("user_id") val userId: String,
    @SerializedName("full_name") val fullName: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("is_new_user") val isNewUser: Boolean = false,
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String
)

data class OtpData(
    @SerializedName("otp_id") val otpId: String,
    @SerializedName("expires_in") val expiresIn: Int
)

data class RefreshData(
    @SerializedName("access_token") val accessToken: String
)

data class ValidateData(
    @SerializedName("user_id") val userId: String,
    @SerializedName("is_valid") val isValid: Boolean
)
```

### 7.3 User DTOs

```kotlin
// data/network/dto/UserDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

data class UserProfile(
    @SerializedName("user_id") val userId: String,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("email") val email: String?,
    @SerializedName("phone") val phone: String?,
    @SerializedName("profile_image_url") val profileImageUrl: String?,
    @SerializedName("emergency_contact") val emergencyContact: String?,
    @SerializedName("member_since") val memberSince: String,
    @SerializedName("is_protection_active") val isProtectionActive: Boolean,
    @SerializedName("auth_provider") val authProvider: String
)

data class UpdateProfileRequest(
    @SerializedName("full_name") val fullName: String? = null,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("profile_image_url") val profileImageUrl: String? = null
)

data class FcmTokenRequest(
    @SerializedName("fcm_token") val fcmToken: String
)
```

### 7.4 Contacts DTOs

```kotlin
// data/network/dto/ContactDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

data class TrustedContact(
    @SerializedName("id") val id: String,
    @SerializedName("name") val name: String,
    @SerializedName("phone") val phone: String,
    @SerializedName("email") val email: String? = null,
    @SerializedName("relationship") val relationship: String? = null,
    @SerializedName("is_primary") val isPrimary: Boolean = false
)

data class AddContactRequest(
    @SerializedName("name") val name: String,
    @SerializedName("phone") val phone: String,
    @SerializedName("email") val email: String? = null,
    @SerializedName("relationship") val relationship: String? = null,
    @SerializedName("is_primary") val isPrimary: Boolean = false
)

data class UpdateContactRequest(
    @SerializedName("name") val name: String? = null,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("relationship") val relationship: String? = null
)
```

### 7.5 SOS DTOs

```kotlin
// data/network/dto/SosDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

data class SosTriggerRequest(
    @SerializedName("trigger_type") val triggerType: String, // "manual", "auto_fall", "auto_shake"
    @SerializedName("latitude") val latitude: Double,
    @SerializedName("longitude") val longitude: Double,
    @SerializedName("accuracy") val accuracy: Float? = null
)

data class SosSendNowRequest(
    @SerializedName("alert_id") val alertId: String
)

data class SosCancelRequest(
    @SerializedName("alert_id") val alertId: String
)

data class SosAlertData(
    @SerializedName("alert_id") val alertId: String,
    @SerializedName("status") val status: String,
    @SerializedName("countdown_seconds") val countdownSeconds: Int? = null,
    @SerializedName("contacts_to_notify") val contactsToNotify: Int? = null
)

data class SosHistoryItem(
    @SerializedName("alert_id") val alertId: String,
    @SerializedName("trigger_type") val triggerType: String,
    @SerializedName("address") val address: String?,
    @SerializedName("status") val status: String,
    @SerializedName("triggered_at") val triggeredAt: String,
    @SerializedName("resolved_at") val resolvedAt: String?
)
```

### 7.6 Location DTOs

```kotlin
// data/network/dto/LocationDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

data class LocationUpdateRequest(
    @SerializedName("latitude") val latitude: Double,
    @SerializedName("longitude") val longitude: Double,
    @SerializedName("accuracy") val accuracy: Float? = null,
    @SerializedName("is_sharing") val isSharing: Boolean = false
)

data class LocationData(
    @SerializedName("latitude") val latitude: Double,
    @SerializedName("longitude") val longitude: Double,
    @SerializedName("address") val address: String?,
    @SerializedName("accuracy") val accuracy: String?,
    @SerializedName("is_sharing") val isSharing: Boolean,
    @SerializedName("recorded_at") val recordedAt: String?
)

data class SharingData(
    @SerializedName("sharing_session_id") val sharingSessionId: String,
    @SerializedName("shared_with") val sharedWith: List<SharedContact>,
    @SerializedName("tracking_url") val trackingUrl: String?
)

data class SharedContact(
    @SerializedName("name") val name: String,
    @SerializedName("phone") val phone: String
)
```

### 7.7 Settings DTOs

```kotlin
// data/network/dto/SettingsDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

data class UserSettings(
    @SerializedName("emergency_number") val emergencyNumber: String,
    @SerializedName("sos_message") val sosMessage: String,
    @SerializedName("shake_sensitivity") val shakeSensitivity: String,
    @SerializedName("battery_optimization") val batteryOptimization: Boolean,
    @SerializedName("haptic_feedback") val hapticFeedback: Boolean
)

data class UpdateSettingsRequest(
    @SerializedName("emergency_number") val emergencyNumber: String? = null,
    @SerializedName("sos_message") val sosMessage: String? = null,
    @SerializedName("shake_sensitivity") val shakeSensitivity: String? = null,
    @SerializedName("battery_optimization") val batteryOptimization: Boolean? = null,
    @SerializedName("haptic_feedback") val hapticFeedback: Boolean? = null
)
```

### 7.8 Device & Support DTOs

```kotlin
// data/network/dto/DeviceDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

data class RegisterDeviceRequest(
    @SerializedName("device_name") val deviceName: String,
    @SerializedName("device_mac") val deviceMac: String,
    @SerializedName("firmware_version") val firmwareVersion: String? = null
)

data class UpdateDeviceStatusRequest(
    @SerializedName("is_connected") val isConnected: Boolean
)

data class DeviceData(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("device_name") val deviceName: String,
    @SerializedName("is_connected") val isConnected: Boolean,
    @SerializedName("battery_level") val batteryLevel: Int? = null,
    @SerializedName("firmware_version") val firmwareVersion: String? = null,
    @SerializedName("signal_strength") val signalStrength: String? = null,
    @SerializedName("last_seen") val lastSeen: String? = null
)

// data/network/dto/SupportDtos.kt
data class FaqItem(
    @SerializedName("id") val id: Int,
    @SerializedName("question") val question: String,
    @SerializedName("answer") val answer: String,
    @SerializedName("category") val category: String,
    @SerializedName("icon") val icon: String
)

data class CreateTicketRequest(
    @SerializedName("subject") val subject: String,
    @SerializedName("message") val message: String
)

data class TicketData(
    @SerializedName("ticket_id") val ticketId: String,
    @SerializedName("subject") val subject: String? = null,
    @SerializedName("status") val status: String,
    @SerializedName("created_at") val createdAt: String
)
```

### 7.9 Protection DTOs

```kotlin
// data/network/dto/ProtectionDtos.kt
package com.yourname.womensafety.data.network.dto

import com.google.gson.annotations.SerializedName

data class ToggleProtectionRequest(
    @SerializedName("is_active") val isActive: Boolean
)

data class ProtectionStatus(
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("activated_at") val activatedAt: String? = null,
    @SerializedName("monitoring_duration_minutes") val monitoringDurationMinutes: Int? = null,
    @SerializedName("bracelet_connected") val braceletConnected: Boolean = false
)

data class SensorDataRequest(
    @SerializedName("sensor_type") val sensorType: String,
    @SerializedName("data") val data: List<SensorReading>,
    @SerializedName("sensitivity") val sensitivity: String
)

data class SensorReading(
    @SerializedName("x") val x: Float,
    @SerializedName("y") val y: Float,
    @SerializedName("z") val z: Float,
    @SerializedName("timestamp") val timestamp: Long
)

data class SensorAnalysisResult(
    @SerializedName("alert_triggered") val alertTriggered: Boolean,
    @SerializedName("alert_id") val alertId: String? = null,
    @SerializedName("confidence") val confidence: Float? = null
)
```

---

## 8. Repository Layer

Repositories abstract the data source (network) from ViewModels.

### 8.1 Base Network Result Wrapper

```kotlin
// data/repository/NetworkResult.kt
package com.yourname.womensafety.data.repository

sealed class NetworkResult<out T> {
    data class Success<T>(val data: T, val message: String? = null) : NetworkResult<T>()
    data class Error(val code: String, val message: String) : NetworkResult<Nothing>()
    data object Loading : NetworkResult<Nothing>()
}
```

### 8.2 Base Repository Helper

```kotlin
// data/repository/BaseRepository.kt
package com.yourname.womensafety.data.repository

import com.google.gson.Gson
import com.yourname.womensafety.data.network.dto.ApiResponse
import retrofit2.Response

abstract class BaseRepository {

    /**
     * Safely execute a Retrofit API call and wrap the result.
     */
    protected suspend fun <T> safeApiCall(
        apiCall: suspend () -> Response<ApiResponse<T>>
    ): NetworkResult<T> {
        return try {
            val response = apiCall()
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null && body.success) {
                    NetworkResult.Success(body.data, body.message)
                } else {
                    val errorMsg = body?.error?.message ?: "Unknown error"
                    val errorCode = body?.error?.code ?: "UNKNOWN"
                    NetworkResult.Error(errorCode, errorMsg)
                }
            } else {
                // Parse error body
                val errorBody = response.errorBody()?.string()
                val apiError = try {
                    Gson().fromJson(errorBody, ApiResponse::class.java)
                } catch (e: Exception) { null }

                NetworkResult.Error(
                    code = apiError?.error?.code ?: "HTTP_${response.code()}",
                    message = apiError?.error?.message ?: response.message()
                )
            }
        } catch (e: java.net.UnknownHostException) {
            NetworkResult.Error("NETWORK_ERROR", "No internet connection")
        } catch (e: java.net.SocketTimeoutException) {
            NetworkResult.Error("TIMEOUT", "Request timed out")
        } catch (e: Exception) {
            NetworkResult.Error("UNKNOWN", e.localizedMessage ?: "An unexpected error occurred")
        }
    }
}
```

### 8.3 Auth Repository

```kotlin
// data/repository/AuthRepository.kt
package com.yourname.womensafety.data.repository

import com.yourname.womensafety.data.local.TokenManager
import com.yourname.womensafety.data.network.api.AuthApiService
import com.yourname.womensafety.data.network.dto.*

class AuthRepository(
    private val authApi: AuthApiService,
    private val tokenManager: TokenManager
) : BaseRepository() {

    suspend fun loginWithEmail(email: String, password: String): NetworkResult<AuthData> {
        val result = safeApiCall {
            authApi.loginWithEmail(EmailLoginRequest(email, password))
        }
        // Save tokens on success
        if (result is NetworkResult.Success) {
            tokenManager.saveTokens(
                accessToken = result.data.accessToken,
                refreshToken = result.data.refreshToken,
                userId = result.data.userId
            )
        }
        return result
    }

    suspend fun registerWithEmail(
        name: String, email: String, password: String
    ): NetworkResult<AuthData> {
        val result = safeApiCall {
            authApi.registerWithEmail(EmailRegisterRequest(name, email, password))
        }
        if (result is NetworkResult.Success) {
            tokenManager.saveTokens(
                accessToken = result.data.accessToken,
                refreshToken = result.data.refreshToken,
                userId = result.data.userId
            )
        }
        return result
    }

    suspend fun sendOtp(phone: String): NetworkResult<OtpData> {
        return safeApiCall { authApi.sendOtp(SendOtpRequest(phone)) }
    }

    suspend fun verifyOtp(phone: String, otpCode: String): NetworkResult<AuthData> {
        val result = safeApiCall {
            authApi.verifyOtp(VerifyOtpRequest(phone, otpCode))
        }
        if (result is NetworkResult.Success) {
            tokenManager.saveTokens(
                accessToken = result.data.accessToken,
                refreshToken = result.data.refreshToken,
                userId = result.data.userId
            )
        }
        return result
    }

    suspend fun logout(): NetworkResult<Unit> {
        val result = safeApiCall { authApi.logout() }
        tokenManager.clearTokens() // Always clear locally
        return result
    }

    suspend fun validateToken(): NetworkResult<ValidateData> {
        return safeApiCall { authApi.validateToken() }
    }
}
```

### 8.4 SOS Repository

```kotlin
// data/repository/SosRepository.kt
package com.yourname.womensafety.data.repository

import com.yourname.womensafety.data.network.api.SosApiService
import com.yourname.womensafety.data.network.dto.*

class SosRepository(
    private val sosApi: SosApiService
) : BaseRepository() {

    suspend fun triggerSos(
        triggerType: String,
        latitude: Double,
        longitude: Double,
        accuracy: Float? = null
    ): NetworkResult<SosAlertData> {
        return safeApiCall {
            sosApi.triggerSos(
                SosTriggerRequest(triggerType, latitude, longitude, accuracy)
            )
        }
    }

    suspend fun sendSosNow(alertId: String): NetworkResult<SosAlertData> {
        return safeApiCall { sosApi.sendSosNow(SosSendNowRequest(alertId)) }
    }

    suspend fun cancelSos(alertId: String): NetworkResult<Unit> {
        return safeApiCall { sosApi.cancelSos(SosCancelRequest(alertId)) }
    }

    suspend fun getSosHistory(): NetworkResult<List<SosHistoryItem>> {
        return safeApiCall { sosApi.getSosHistory() }
    }
}
```

> **Pattern:** Create similar repositories for `ContactsRepository`, `LocationRepository`, `SettingsRepository`, `DeviceRepository`, and `SupportRepository` following the exact same pattern.

---

## 9. ViewModels

ViewModels bridge Repositories with Compose UI. Each screen that needs backend data gets a ViewModel.

### 9.1 Auth ViewModel (Login Screens)

```kotlin
// ui/viewmodels/AuthViewModel.kt
package com.yourname.womensafety.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourname.womensafety.data.repository.AuthRepository
import com.yourname.womensafety.data.repository.NetworkResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AuthUiState(
    val isLoading: Boolean = false,
    val isSuccess: Boolean = false,
    val errorMessage: String? = null
)

class AuthViewModel(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun loginWithEmail(email: String, password: String) {
        viewModelScope.launch {
            _uiState.value = AuthUiState(isLoading = true)
            when (val result = authRepository.loginWithEmail(email, password)) {
                is NetworkResult.Success -> {
                    _uiState.value = AuthUiState(isSuccess = true)
                }
                is NetworkResult.Error -> {
                    _uiState.value = AuthUiState(errorMessage = result.message)
                }
                is NetworkResult.Loading -> {}
            }
        }
    }

    fun sendOtp(phone: String) {
        viewModelScope.launch {
            _uiState.value = AuthUiState(isLoading = true)
            when (val result = authRepository.sendOtp(phone)) {
                is NetworkResult.Success -> {
                    _uiState.value = AuthUiState(isSuccess = true)
                }
                is NetworkResult.Error -> {
                    _uiState.value = AuthUiState(errorMessage = result.message)
                }
                is NetworkResult.Loading -> {}
            }
        }
    }

    fun verifyOtp(phone: String, otpCode: String) {
        viewModelScope.launch {
            _uiState.value = AuthUiState(isLoading = true)
            when (val result = authRepository.verifyOtp(phone, otpCode)) {
                is NetworkResult.Success -> {
                    _uiState.value = AuthUiState(isSuccess = true)
                }
                is NetworkResult.Error -> {
                    _uiState.value = AuthUiState(errorMessage = result.message)
                }
                is NetworkResult.Loading -> {}
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
```

### 9.2 SOS ViewModel

```kotlin
// ui/viewmodels/SosViewModel.kt
package com.yourname.womensafety.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourname.womensafety.data.repository.NetworkResult
import com.yourname.womensafety.data.repository.SosRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class SosUiState(
    val alertId: String? = null,
    val isSending: Boolean = false,
    val isSent: Boolean = false,
    val isCancelled: Boolean = false,
    val errorMessage: String? = null
)

class SosViewModel(
    private val sosRepository: SosRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(SosUiState())
    val uiState: StateFlow<SosUiState> = _uiState

    fun triggerSos(latitude: Double, longitude: Double) {
        viewModelScope.launch {
            when (val result = sosRepository.triggerSos("manual", latitude, longitude)) {
                is NetworkResult.Success -> {
                    _uiState.value = SosUiState(alertId = result.data.alertId)
                }
                is NetworkResult.Error -> {
                    _uiState.value = SosUiState(errorMessage = result.message)
                }
                is NetworkResult.Loading -> {}
            }
        }
    }

    fun sendNow() {
        val alertId = _uiState.value.alertId ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSending = true)
            when (sosRepository.sendSosNow(alertId)) {
                is NetworkResult.Success -> {
                    _uiState.value = _uiState.value.copy(isSending = false, isSent = true)
                }
                is NetworkResult.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isSending = false,
                        errorMessage = "Failed to send SOS"
                    )
                }
                is NetworkResult.Loading -> {}
            }
        }
    }

    fun cancelSos() {
        val alertId = _uiState.value.alertId ?: return
        viewModelScope.launch {
            when (sosRepository.cancelSos(alertId)) {
                is NetworkResult.Success -> {
                    _uiState.value = _uiState.value.copy(isCancelled = true)
                }
                is NetworkResult.Error -> {
                    _uiState.value = _uiState.value.copy(errorMessage = "Failed to cancel")
                }
                is NetworkResult.Loading -> {}
            }
        }
    }
}
```

---

## 10. Screen-by-Screen Integration

### 10.1 SignInWithEmail — Before & After

**BEFORE (current — no backend):**
```kotlin
// Current: saves login flag locally, no real auth
Button(onClick = {
    val sharedPref = context.getSharedPreferences("raksha_prefs", Context.MODE_PRIVATE)
    sharedPref.edit().putBoolean("is_logged_in", true).apply()
    navController.navigate("dashboard") { popUpTo(0) { inclusive = true } }
})
```

**AFTER (with Flask backend):**
```kotlin
@Composable
fun SignInWithEmail(
    navController: NavController,
    authViewModel: AuthViewModel  // injected or created via viewModel()
) {
    val context = LocalContext.current
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val uiState by authViewModel.uiState.collectAsState()

    // Navigate on successful login
    LaunchedEffect(uiState.isSuccess) {
        if (uiState.isSuccess) {
            navController.navigate("dashboard") {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    // Show error snackbar
    LaunchedEffect(uiState.errorMessage) {
        uiState.errorMessage?.let { message ->
            // Show a Snackbar or Toast
            Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
            authViewModel.clearError()
        }
    }

    // ... your existing UI code ...

    Button(
        onClick = {
            if (email.isNotBlank() && password.isNotBlank()) {
                authViewModel.loginWithEmail(email, password)  // ← API call
            }
        },
        enabled = !uiState.isLoading  // Disable while loading
    ) {
        if (uiState.isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                color = Color.White,
                strokeWidth = 2.dp
            )
        } else {
            Text("Sign In", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
        }
    }
}
```

### 10.2 SignInWithPhone — Before & After

**AFTER:**
```kotlin
@Composable
fun SignInWithPhone(
    navController: NavController,
    authViewModel: AuthViewModel
) {
    var phoneNumber by remember { mutableStateOf("") }
    val uiState by authViewModel.uiState.collectAsState()

    LaunchedEffect(uiState.isSuccess) {
        if (uiState.isSuccess) {
            navController.navigate("verify_otp")
        }
    }

    Button(onClick = {
        if (phoneNumber.isNotBlank()) {
            authViewModel.sendOtp(phoneNumber)  // ← Calls Flask: POST /api/auth/send-otp
        }
    }) {
        if (uiState.isLoading) {
            CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White)
        } else {
            Text("Send OTP")
        }
    }
}
```

### 10.3 VerifyOTPScreen — Before & After

**AFTER:**
```kotlin
@Composable
fun VerifyOTPScreen(
    navController: NavController,
    authViewModel: AuthViewModel,
    phone: String  // pass phone from previous screen via nav args
) {
    var otpCode by remember { mutableStateOf(listOf("", "", "", "")) }
    val uiState by authViewModel.uiState.collectAsState()

    LaunchedEffect(uiState.isSuccess) {
        if (uiState.isSuccess) {
            navController.navigate("dashboard") {
                popUpTo("login") { inclusive = true }
            }
        }
    }

    // Verify button
    Button(onClick = {
        val code = otpCode.joinToString("")
        if (code.length == 4) {
            authViewModel.verifyOtp(phone, code)  // ← Calls Flask: POST /api/auth/verify-otp
        }
    }) {
        Text("Verify & Proceed")
    }

    // Resend button
    TextButton(onClick = {
        authViewModel.sendOtp(phone)  // ← Calls Flask: POST /api/auth/resend-otp
        otpCode = listOf("", "", "", "")
    }) {
        Text("Resend Code", color = Color.Gray)
    }
}
```

### 10.4 SOSAlertScreen — Before & After

**AFTER:**
```kotlin
@Composable
fun SOSAlertScreen(
    onSafe: () -> Unit,
    sosViewModel: SosViewModel
) {
    var ticks by remember { mutableIntStateOf(10) }
    val uiState by sosViewModel.uiState.collectAsState()

    // Trigger SOS on screen load (get current location first)
    LaunchedEffect(Unit) {
        // Get current GPS coordinates from FusedLocationProviderClient
        val location = getCurrentLocation()
        sosViewModel.triggerSos(location.latitude, location.longitude)
    }

    // Countdown timer
    LaunchedEffect(Unit) {
        while (ticks > 0) {
            delay(1000L)
            ticks--
        }
        // Countdown reached 0 — send SOS
        if (!uiState.isCancelled) {
            sosViewModel.sendNow()  // ← Calls Flask: POST /api/sos/send-now
        }
    }

    // Handle cancel (navigate back on success)
    LaunchedEffect(uiState.isCancelled) {
        if (uiState.isCancelled) onSafe()
    }

    // "I'M SAFE" button
    Button(onClick = {
        sosViewModel.cancelSos()  // ← Calls Flask: POST /api/sos/cancel
    }) {
        Text("I'M SAFE")
    }

    // "SEND SOS NOW" button
    Button(onClick = {
        sosViewModel.sendNow()  // ← Calls Flask: POST /api/sos/send-now
    }) {
        Text("SEND SOS NOW")
    }
}
```

### 10.5 ProfileScreen — Before & After

**AFTER:**
```kotlin
@Composable
fun ProfileScreen(
    navController: NavController,
    profileViewModel: ProfileViewModel
) {
    val profileState by profileViewModel.profileState.collectAsState()

    LaunchedEffect(Unit) {
        profileViewModel.loadProfile()  // ← Calls Flask: GET /api/user/profile
    }

    when (val state = profileState) {
        is NetworkResult.Loading -> {
            // Show shimmer/loading skeleton
        }
        is NetworkResult.Success -> {
            val profile = state.data
            // Replace hardcoded values:
            Text(profile.fullName)         // was: "Jessica Parker"
            Text(profile.email ?: "")      // was: "jessica.parker@email.com"
            InfoRow("Phone Number", profile.phone ?: "Not set")
            InfoRow("Emergency Contact", profile.emergencyContact ?: "Not set")
            InfoRow("Member Since", profile.memberSince)
        }
        is NetworkResult.Error -> {
            // Show error state with retry button
        }
    }

    // Logout
    Button(onClick = {
        profileViewModel.logout()  // ← Calls Flask: POST /api/auth/logout
        navController.navigate("login") { popUpTo(0) { inclusive = true } }
    })
}
```

### 10.6 SettingsScreen — Before & After

**AFTER:**
```kotlin
@Composable
fun SettingsScreen(
    navController: NavController,
    settingsViewModel: SettingsViewModel
) {
    val settingsState by settingsViewModel.settings.collectAsState()

    LaunchedEffect(Unit) {
        settingsViewModel.loadSettings()  // ← GET /api/settings
    }

    // Settings values from backend instead of local state
    var sensitivity by remember(settingsState) {
        mutableStateOf(settingsState?.shakeSensitivity ?: "Medium")
    }

    Button(onClick = {
        settingsViewModel.saveSettings(
            UpdateSettingsRequest(
                shakeSensitivity = sensitivity,