#include "BluetoothSerial.h"
BluetoothSerial SerialBT;

#define BUTTON_PIN 23

bool lastState = HIGH;
unsigned long lastPressMillis = 0;
const unsigned long DEBOUNCE_MS = 50;   // just enough to filter contact bounce

void setup() {
  Serial.begin(115200);
  SerialBT.begin("ESP32_SOS_DEVICE");   // must match app
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.println("Bluetooth Ready...");
}

void loop() {
  bool currentState = digitalRead(BUTTON_PIN);
  unsigned long now = millis();

  if (lastState == HIGH && currentState == LOW) {
    // Falling edge — fire only if past debounce window (non-blocking)
    if ((now - lastPressMillis) >= DEBOUNCE_MS) {
      Serial.println("SOS_TRIGGER_RANDOM_MESSAGE");
      SerialBT.println("SOS_TRIGGER_RANDOM_MESSAGE");
      lastPressMillis = now;
    }
  }

  lastState = currentState;
}