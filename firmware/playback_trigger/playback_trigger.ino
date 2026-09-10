// One serial command produces one one-second Avisoft TRG pulse.
//
// Wiring for a classic 5 V Arduino Nano:
//   D8  -> Player 116H TRG tip
//   GND -> Player 116H TRG sleeve

// The Player supplies its own pull-up. Releasing D8 as an input leaves the
// trigger inactive; driving D8 low acts like pressing the TRG button.

const byte TRIGGER_PIN = 8;
const unsigned long PULSE_DURATION_MS = 1000;

bool pulseActive = false;
unsigned long pulseStartedAt = 0;

void releaseTrigger() {
  pinMode(TRIGGER_PIN, INPUT);
  digitalWrite(TRIGGER_PIN, LOW);  // Keep the Arduino pull-up disabled.
}

void setup() {
  releaseTrigger();
  Serial.begin(9600);
  Serial.println("READY");
}

void loop() {
  if (pulseActive && millis() - pulseStartedAt >= PULSE_DURATION_MS) {
    releaseTrigger();
    pulseActive = false;
    Serial.println("DONE");
  }

  while (Serial.available() > 0) {
    const char command = Serial.read();

    if (command != 'T') {
      continue;
    }

    if (pulseActive) {
      Serial.println("BUSY");
      continue;
    }

    digitalWrite(TRIGGER_PIN, LOW);
    pinMode(TRIGGER_PIN, OUTPUT);
    pulseStartedAt = millis();
    pulseActive = true;
    Serial.println("START");
  }
}
