# Passive playback

The passive-playback protocol requests one Avisoft playback every 120 seconds.
Avisoft owns the playlist; this repository controls only trigger timing.

## Arduino

Upload `firmware/playback_trigger/playback_trigger.ino` to a classic 5 V
Arduino Nano using these Arduino IDE settings:

- board: Arduino Nano
- processor: ATmega328P, or ATmega328P (Old Bootloader) for older clones
- port: COM3 on the current development computer

Wire Nano D8 to the Player 116H TRG tip and Nano GND to the TRG sleeve. The
firmware releases D8 while idle and pulls it to ground for one second when it
receives `T` at 9600 baud.

## Run

Confirm the resolved settings:

```powershell
conda activate audiomoth
python -m steg_song check --config protocols/passive_playback.toml --rig config/rig.local.toml
```

Then start a new session:

```powershell
python -m steg_song run --config protocols/passive_playback.toml --rig config/rig.local.toml --session passive-test
```

The first trigger occurs after 120 seconds. For a short bench test, copy
`protocols/passive_playback.toml` outside the repository and set
`interval_seconds = 5` in that copy.

The command window and `playback_events.csv` report `PORT_OPEN`,
`TRIGGER_SENT`, `READY`, `START`, `DONE`, or `BUSY`. A normal trigger produces
one `TRIGGER_SENT`, one `START`, and one `DONE`; `BUSY` indicates an unexpected
duplicate request.

## Avisoft playlist settings

For the current repeating bench test:

- check **stop after each file** so one trigger plays exactly one file
- check the playlist **loop mode** so the next trigger wraps to the first item
  after the final item
- leave playlist delay and randomization off because trigger timing and playlist
  order are controlled elsewhere

Playlist loop mode does not replay one file continuously. It only controls what
happens after the last playlist item. For a deliberately finite, one-pass
experiment, uncheck it instead.
