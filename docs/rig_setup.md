# Rig setup

Use this AudioMoth configuration for song-detection tests:

- USB microphone sample rate: **250 kHz**
- gain: **medium**
- low gain mode: **enabled**
- physical switch: **CUSTOM**

Yes, low gain mode with medium gain is the configuration carried forward from
the earlier rig work. Keep it fixed while tuning the detector because changing
gain changes the full-scale RMS values and therefore the meaning of
`rms_threshold`.

Before each run:

1. Verify these values in the AudioMoth USB Microphone App.
2. Verify any device-side filters or advanced settings under CUSTOM; do not let
   them change silently between sessions.
3. Close the AudioMoth app and any other application using the microphone.
4. Keep microphone position and orientation fixed and record them with the
   experiment notes.
5. Run the protocol configuration check before starting Bonsai.

Set the absolute repository location once in `rig.local.toml`. Portable protocol
configs use it to resolve their relative Bonsai workflow paths:

```toml
[steg_song]
repo_root = "C:/Users/xizheng/Projects/steg-song-bot"
```

For playback, set the Nano serial connection in `rig.local.toml`:

```toml
[arduino_trigger]
port = "COM3"
baud_rate = 9600
```

The port is rig-specific. Close Arduino Serial Monitor before starting Bonsai
because only one program can own the serial port.
