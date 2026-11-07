// Optional reference sketch. Keep your working wiring/sketch unless adapting
// its serial output is necessary. Libraries: Adafruit BME280 + Unified Sensor.
// Arduino IDE board selection supplied by user: Arduino UNO.
// Confirm the physical board and choose its serial port before uploading.
// BME280 voltage/pins depend on board
// and breakout: do not assume every bare sensor or module is 5 V tolerant.
#include <Wire.h>
#include <Adafruit_BME280.h>

Adafruit_BME280 bme;

void setup() {
  Serial.begin(9600);
  if (!bme.begin(0x76) && !bme.begin(0x77)) {
    Serial.println("BME280 not detected: check your existing wiring/address");
    while (true) delay(1000);
  }
}

void loop() {
  float t = bme.readTemperature();
  float h = bme.readHumidity();
  float p = bme.readPressure() / 100.0F; // Pa -> hPa
  if (!isnan(t) && !isnan(h) && !isnan(p)) {
    Serial.print("{\"temperature\":"); Serial.print(t, 2);
    Serial.print(",\"humidity\":"); Serial.print(h, 2);
    Serial.print(",\"pressure\":"); Serial.print(p, 2);
    Serial.println("}");
  }
  delay(5000);
}
