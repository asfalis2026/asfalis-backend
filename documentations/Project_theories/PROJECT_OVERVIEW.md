# Project Overview: Asfalis Backend

This document provides a high-level overview of the **Asfalis Backend** architecture, features, and the technologies used in development.

## 🏗️ Backend Architecture

The Asfalis backend is built as a modular monolithic application using a structured **Flask** architecture. It implements a clear separation of concerns to ensure maintainability and scalability.

### Core Structure:
- **`app/routes/`**: Handles incoming HTTP requests and responses (API Endpoints).
- **`app/services/`**: Contains the core business logic, including machine learning inference, notification dispatch, and external API integrations.
- **`app/models/`**: Defines the database schema using SQLAlchemy models.
- **`app/schemas/`**: Manages data validation and serialization/deserialization (Marshmallow).
- **`app/sockets/`**: Facilitates real-time, bidirectional communication using Flask-SocketIO.
- **`app/utils/`**: General helper functions and utility modules.

---

## 🚀 Key Features

### 1. Auto SOS (Safety Protection)
- **ML-Powered Monitoring**: Uses a trained Scikit-learn model to analyze real-time accelerometer and gyroscope data from connected devices.
- **Danger Prediction**: Detects sudden falls or unusual motion patterns with configurable sensitivity (High, Medium, Low).
- **Self-Training Loop**: Automatically saves incoming sensor data for future model retraining and utilizes user feedback to improve accuracy over time.

### 2. Emergency Alert System
- **Multi-Channel Dispatch**: Sends SOS alerts via SMS, WhatsApp (Twilio), and Push Notifications (Firebase Cloud Messaging).
- **Manual & Auto Trigger**: Supports both manual SOS triggers and automated triggers based on ML analysis.
- **Cancellation Countdown**: Provides a grace period for users to cancel false alarms before emergency contacts are notified.

### 3. Device & Location Management
- **IoT Integration**: Manages connections with hardware sensors/bracelets.
- **Real-Time Tracking**: Persists and resolves user GPS coordinates to provide accurate location data during emergencies.

### 4. Security & User Management
- **Secure Authentication**: Implements JWT-based authentication for secure API access.
- **Contact Management**: Allows users to manage emergency contacts who receive alerts during an SOS event.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.x |
| **Web Framework** | Flask |
| **Database** | PostgreSQL (hosted on Supabase) |
| **ORM** | Flask-SQLAlchemy |
| **Migrations** | Flask-Migrate (Alembic) |
| **Machine Learning** | Scikit-learn, Numpy, Pandas, Joblib |
| **Real-time** | Flask-SocketIO |
| **Notifications** | Firebase Admin SDK (FCM), Twilio (SMS/WhatsApp) |
| **Authentication** | Flask-JWT-Extended |
| **Environment** | Docker, Docker-compose |

---

## 🔧 Model & Data Pipeline

The backend maintains a dynamic ML pipeline:
1. **Inference**: High-frequency sensor data is processed through feature extraction (17 statistical features) and fed into the active model.
2. **Persistence**: Sensor windows are stored in the database for longitudinal analysis.
3. **Training**: New models can be trained on gathered data to adapt to specific user behaviors or updated algorithms.
