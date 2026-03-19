# Asfalis — Intelligent ML-Enabled IoT System for Women's Safety

> **Project:** Asfalis Women Safety Platform
> **Version:** 2.0 (Current)
> **Last Updated:** 13 March 2026
> **Status:** Software & ML Core Fully Implemented; Hardware Integration Planned

---

## Abstract

Women's safety remains a critical societal concern, demanding intelligent, reliable, and rapid-response technological solutions. This project presents **Asfalis** — an Intelligent ML-Enabled Safety System for Women that integrates a production-grade Android application, a Flask-based backend API, a Supabase PostgreSQL database, and a robust scikit-learn machine learning pipeline to provide multi-layered, real-time personal protection.

The system currently operates across two active safety layers, with two more planned for future hardware integration:

1. **Manual SOS** — one-tap trigger with a 10-second countdown and false-alarm cancellation
2. **Auto SOS** — accelerometer and gyroscope sensor fusion classified by a server-side ML model; alerts fire automatically on sustained anomalous motion
3. *(Future Scope)* **IoT Wearable SOS** — hardware trigger via Bluetooth for phone-less SOS initiation
4. *(Future Scope)* **Proximity SOS** — BLE RSSI monitoring to detect when a paired wearable forcibly moves beyond 5 m from the phone

The backend communicates with trusted emergency contacts via Twilio WhatsApp and SMS with a live Google Maps link. A JWT-secured REST API manages authentication (phone-number-only, OTP-verified), SOS lifecycle governance, and intricate ML model versioning. The backend maintains an ongoing ground-truth dataset of over 7,500+ verified rows (comprising structured `MEDIUM_DANGER`, `MEDIUM_FALL_CLEANED`, and `MEDIUM_SAFE` observations), allowing continuous active retraining of the scikit-learn Random Forest model immediately within the database architecture. A one-device login policy with a 12-hour handset transfer window prevents unauthorised account access.

---

## Chapter 1 — Introduction

The security of women in both public and private spaces is a critical societal issue. Conventional emergency systems depend on manual initiation, which is impractical under physical constraint, panic, or sudden assault. Advances in smartphones and machine learning now make it feasible to build systems that detect emergencies automatically and dispatch alerts within seconds — without requiring the user to unlock their phone.

### 1.1 Background and Motivation

Most safety applications fail in real emergencies because they require deliberate user action. The user may be unconscious, physically restrained, or too distressed to operate a touchscreen. Modern Android smartphones carry IMU sensors (accelerometer and gyroscope) capable of detecting falls, shakes, and sudden impacts with high fidelity. When combined with a cloud notification backend and machine learning pipelines, these sensors enable autonomous, multi-layered emergency detection that does not depend on active user involvement.

The Asfalis project was motivated by identifying specific gaps in existing solutions:

- **No automation** — existing apps are purely manual trigger systems
- **No data-driven intelligence** — they lack mechanisms to collect, verify, and retrain using historical sensor streams
- **No hardware expansion architecture** — no foundational support to connect external wearable triggers
- **No false-alarm mitigation** — automated systems without cancellation windows generate alert fatigue among contacts

### 1.2 Purpose of this Study

This report documents the software and ML logic architecture of the Asfalis system. Its goals are to:

- Continuously monitor motion data using smartphone IMU sensors
- Classify motion as NORMAL or DANGER using a robust server-deployed Random Forest ML model
- Implement continuous ML delivery by seeding over 7,549 rows of verified CSV data into a Supabase PostgreSQL database for dynamic native retraining
- Execute manual and automatic (ML) SOS alerts, while establishing protocol foundations for future wearable/proximity triggers
- Notify trusted contacts via WhatsApp and SMS with GPS coordinates
- Enforce security through JWT authentication, one-device login, and OTP-verified contacts

---

## Chapter 2 — Literature Overview

### 2.1 Existing Technologies for Women's Safety

Current tools include mobile SOS apps (Nirbhaya, bSafe, Raksha), GPS panic buttons, and standalone wearable alarms. These systems share a critical limitation: they require manual activation. When a user is incapacitated or unable to reach their device, these systems provide no protection. They also lack motion classification, backend audit trails, or contact verification workflows.

### 2.2 IoT and Wearable-Based Safety Systems

While wearables have been explored for remote SOS, existing products function as isolated trigger devices with no awareness of the surrounding user context or phone-side ML layers. Asfalis outlines the foundation to resolve this limitation through its backend `device` API schema prepared for future smart-band integrations.

### 2.3 Machine Learning for Motion Detection

Deployments of robust ML models in actual safety products remain rare due to dataset imbalance, API integration latency, and continuous training challenges.

Asfalis implements a dense production pipeline using **scikit-learn** deployed on Flask. The model handles a 40-reading sliding-window sensor stream and computes 17 distinct statistical features per window (mean, std, min, max, squared-sums, and sensor-type one-hot encoding). Validated against robust testing data (`MEDIUM_DANGER`, `MEDIUM_FALL_CLEANED`, `MEDIUM_SAFE`), the active Random Forest (100 estimators) consistently achieves >92% validation accuracy. 

### 2.4 Identified Research Gaps

| Gap | Asfalis Solution |
|---|---|
| Manual-only activation | Auto SOS via continuous ML stream integration |
| Lack of retraining schema | Natively integrated DB pipeline syncing 7,500+ CSV dataset rows |
| No false-alarm cancellation | 10-second countdown on all SOS paths to prevent fatigue |
| No wearable-phone integration | Fully prepared backend protocol (IoT wearable marked for future release) |
| No contact verification | OTP via Twilio SMS before contact is added |
| Single alert channel | WhatsApp and SMS alongside a Live Maps link via Twilio |

---

## Chapter 3 — Problem Definition and Objectives

### 3.1 Problem Definition

Existing safety systems fail in three scenarios:
1. The user **cannot reach or operate** the phone (physical restraint, unconsciousness)
2. The user **reaches the phone but hesitates** due to fear of false alarm — no cancellation window exists
3. The underlying data **never improves** — systems lack mechanisms to aggregate real-world verified falls vs. safe movements to improve classification reliability.

### 3.2 Objectives

- Detect anomalous motion actively using smartphone accelerometer and gyroscope data
- Classify sensor windows as NORMAL or DANGER using a scikit-learn Random Forest model
- Build a robust data ingestion pipeline that syncs high-fidelity dataset records directly into a Supabase PostgreSQL schema for model self-improvement
- Implement core independent SOS trigger pathways: manual and auto (ML)
- Provide a unified 10-second countdown and cancellation flow on every trigger path
- Notify trusted contacts via Twilio WhatsApp and SMS with Google Maps GPS link
- Secure the entire system: JWT authentication, OTP-verified contacts, and IMEI-bound one-device login

### 3.3 Scope of the Project

#### Implemented Software & ML Core (Current Version)

- Android app (Kotlin, Jetpack Compose, Material 3)
- Real-time smartphone Auto-SOS and Manual SOS integration 
- Flask REST API with complete SOS lifecycle and state governance
- **Database & Model Versioning Engine**: Configured to sync validated sensor logs seamlessly to a Supabase PostgreSQL instance (`sensor_training_data`), accompanied by a real-time table (`MLModel`) containing serialized versions of deployed predictive models and their baseline accuracy scores.
- **Machine Learning Core**: 100-tree scikit-learn Random Forest pipeline extracting 17 unique statistical features per 40-reading sensor window, trained iteratively over 7,500+ categorized records.
- Twilio WhatsApp and SMS alert delivery
- Configurable One-device login with IMEI binding and 12-hour handset transfer
- Live location sharing via WebSocket (Socket.IO)

#### Future Scope (Hardware Expansion)

- ESP32 / Custom PCB v2 hardware (Nordic nRF52810, BLE 5.0) integration for a physical wrist-worn SOS button
- BLE RSSI proximity monitoring with median-filtered distance estimation (to alert if the wearable is forcibly distanced from the phone)
- On-device lightweight ML inference (TensorFlow Lite)

---

## Chapter 4 — Feasibility Study

### 4.1 Technical Feasibility

The entire software stack uses production-grade, well-maintained technologies. ML inference runs entirely server-side (Flask), drastically minimizing the app’s execution load and preserving battery. Expanding the schema limits to include Supabase PostgreSQL allows the data architecture to effortlessly process large bulk-insertions scaling indefinitely. 

### 4.2 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Mobile App | Android, Kotlin, Jetpack Compose | UI, sensor windowing & streaming, SOS flows |
| Backend API | Python 3, Flask | REST endpoints, JWT security, lifecycle logic |
| Database | PostgreSQL (Supabase), SQLAlchemy ORM | Storing users, SOS logs, dataset streams, and active model blobbing |
| ML Pipeline | scikit-learn, Pandas, NumPy, joblib | Advanced feature extraction, Random Forest continuous training |
| Networking | Retrofit 2.11, OkHttp | REST API calls, interceptors |
| Local Storage | Jetpack DataStore, SharedPreferences | Persistent auth and device profile state |
| Push Notifications | Firebase Cloud Messaging (FCM) | Real-time immediate alert pushes |
| Live Location | Socket.IO 2.1.1 (WebSocket) | GPS tracking stream during an active SOS |
| Alert Delivery | Twilio WhatsApp API and SMS | Remote trusted contact notification |
| Hardware / IoT | (Future Scope) Custom Wearable | Button-to-Bluetooth triggering protocols |

---

## Chapter 5 — System Design

### 5.1 System Architecture

The Android app streams processed sensor data via Retrofit to the Flask server APIs. Four independent safety mechanisms coordinate with the foundational backend architecture. The Flask backend exposes endpoints mapping specific functionality:

- `/api/auth/` — phone-only JWT auth, OTP, IMEI device binding
- `/api/sos/` — trigger, cancel, safe, send-now, structured history
- `/api/contacts/` — OTP-verified trusted contact management
- `/api/protection/` — active sensor ML predictions (`predict`) and programmatic model retraining loops (`train-model`)
- `/api/device/` — endpoints drafted and ready for Future Scope IoT hardware pairing (register, status, disconnect)

### 5.2 Software Engineering Paradigm

The project executes an iterative incremental model:

| Iteration | Scope | Status |
|---|---|---|
| 1 | Android app, Flask API, Manual SOS, Twilio alerts | Complete |
| 2 | Machine Learning Integration, Supabase dataset seeding, DB model provisioning | Complete |
| 3 | Security Layer (IMEI login, OTP contacts, payload security) | Complete |
| 4 | Custom wearable hardware (BLE 5.0), hardware API testing, proximity validation | Planned (Future) |

### 5.3 Unified SOS State Machine

Every active trigger path (manual or ML automatic) routes through a synchronized backend state machine:

- **IDLE** — normal application flow
- **COUNTDOWN** — configurable 10-second verification phase; users can cancel to suppress the alert immediately
- **DISPATCHED** — WhatsApp, SMS, and FCM channels trigger and dispatch parallel payload deliveries 
- **RESOLVED** — safe marker received, ending the emergency protocol and saving the closure timestamp

### 5.4 Backend ML Data Flow

Auto SOS classification bridges multiple components. Raw IMU signals collected on the Android device are dynamically chunked into sets. The `/api/protection/predict` API utilizes the `extract_features()` heuristic logic (deriving 17 properties from 40 elements) and applies the active predictive model sourced directly from the `MLModel` Database table (falling back to a local `model.pkl` in case of offline deployment).

For persistent accuracy, the backend supports `seed_training_data_from_csv.py`, a robust chunking script capable of converting local physical CSV traces (`MEDIUM_DANGER`, `MEDIUM_FALL_CLEANED`, `MEDIUM_SAFE`) into structured standard entries in the `sensor_training_data` table tied securely to a verified user profile.

### 5.5 Future Scope: IoT Wearable & Proximity Monitoring

While the ML and backend components are fully deployed, corresponding hardware interfaces are reserved for future scope. When implemented:
- **Wearable Flow:** The wearable will transmit triggering messages over Bluetooth SPP. The device parses inter-frame gaps allowing single taps (Trigger SOS) and double taps (Cancel SOS).
- **Proximity Flow:** BLE RSSI polling calculates physical distance. Median filtration masks multi-path noise signals; if the device sustains disconnection boundaries continuously (>5 m), the proximity alert escalates independently.

---

## Chapter 6 — System Analysis

### 6.1 Limitations of Existing Systems

| Limitation | Impact | Asfalis Resolution |
|---|---|---|
| Manual-only SOS | Useless if user incapacitated | Employs verified server-side Random Forest ML monitoring |
| No prediction model tracking | Models rot without updates | Directly seeds datasets and ML binaries into Supabase |
| No cancellation window | Alerts fatigue contacts | Shared 10s countdown flow uniformly blocks false alarms |
| Single notification setup | Fails if data networking drops | Integrates parallel Twilio SMS & WhatsApp delivery |
| Loose device verification | Hijackers can invoke alerts | IMEI bound identity transfers via 12-hour grace period |

### 6.2 Feature Comparison

| Feature | Existing Solutions | Asfalis |
|---|---|---|
| Auto SOS via ML | No | **Yes** — Random Forest executing on stream sequences |
| In-Database Model Retraining | No | **Yes** — Extensible Supabase ML blob and data storage |
| False alarm cancellation | No | **Yes** — Centralized countdown execution layer |
| WhatsApp & True GPS maps | Rare | **Yes** — Twilio integrations driving Google Maps links |
| Contact OTP verification | No | **Yes** — Strict Twilio authorization limits shadow entries |
| Wearable SOS / Proximity | Basic | **Planned (Future Scope)** — Infrastructure structured and ready |

---

## Chapter 7 — Summary, Future Scope and Conclusion

### 7.1 Summary

Asfalis is a comprehensively implemented software and data-intelligence platform redefining women's safety. It currently executes fully autonomous sensor-based Auto SOS capabilities powered by a sophisticated scikit-learn Random Forest model processing 40-reading sensor chunks dynamically. To ensure scaling accuracy, the backend embeds an optimized architecture natively bridging validated CSV motion arrays into a Supabase PostgreSQL tracking system (`sensor_training_data`). Models trained from this data are securely persisted into the active database infrastructure (`MLModel`). All emergencies undergo a critical 10-second countdown allowing safe cancellation before dispatching comprehensive Twilio WhatsApp, SMS, and Firebase pushes containing Live Google Maps tracking links.

### 7.2 Future Scope

While the core prediction engine and web-application layers are operational, expanding the platform natively relies on upcoming components:
- **Custom Hardware Manufacturing** — Producing the nRF52810-based wristband (BLE 5.0, 28 x 18 mm) to natively communicate with the drafted `/api/device/` endpoints
- **BLE GATT Integration** — Moving beyond conventional Bluetooth SPP into scalable GATT notification channels 
- **On-device ML Optimization** — Compressing the backend's verified Random Forest models into TensorFlow Lite implementations executed locally on the Android device for low-latency zero-network functionality
- **SOS Analytics Dashboard** — Detailed web-portals tracking false-alarm ratios, geographical emergency distribution, and system response times 

### 7.3 Conclusion

The Asfalis project successfully proves that autonomous safety networks powered by verifiable, database-driven machine learning models are efficiently achievable using robust modern architectures. By centering its logic around a scalable Flask REST API, Supabase relational mapping, and scikit-learn models natively interacting with smartphone IMUs, the platform removes the crippling dependency on manual user intervention. The architecture's precise modularity effectively ensures that future augmentations — such as IoT wearables or localized Android ML inferences — can be attached to the existing foundation without reinventing the core emergency governance system.
