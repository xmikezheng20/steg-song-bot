# steg-song-bot

Closed-loop song experiments for *Scotinomys teguina*, built as a set of small
protocols around Bonsai.

The repository is being rebuilt protocol by protocol. Recording, live song
detection and passive playback triggering are the first protocols.

## Repository layout

```text
bonsai/components/  Shared detector logic
bonsai/protocols/   Protocol workflows
config/             Rig-computer configuration
protocols/          Protocol configuration profiles
steg_song/          Configuration and Bonsai launcher
```

Rig configuration describes the computer and attached hardware. Protocol
configuration describes experimental behavior. A run combines exactly one rig
file with one protocol file and saves the fully resolved configuration beside
its output.

## Configure this computer

Copy `config/rig.example.toml` to `config/rig.local.toml` and set:

- the Bonsai executable;
- the exact AudioMoth device name shown by Bonsai;
- the hardware sample rate and format;
- the directory where session folders should be created.

`rig.local.toml` is ignored because device names and storage paths are specific
to one computer.

## Check the recording protocol

Python 3.11 or newer is required by the launcher.

```powershell
conda activate audiomoth
python -m steg_song check recording --rig config/rig.local.toml
```

This validates the configuration and prints all derived values without opening
Bonsai or creating a session.

## Record

```powershell
python -m steg_song run recording --rig config/rig.local.toml --session mouse-001
```

The default opens and starts Bonsai so the incoming signal can be inspected.
Add `--headless` to run without the editor. The launcher creates a new session
directory and refuses to reuse an existing one.

For the first local test, close any other application using the microphone,
start a new session, inspect the `AudioCapture` visualizer for 10–20 seconds,
then stop Bonsai normally with Shift+F5. The session directory should contain
`run.json` and a timestamped `audio*.wav`. A short run produces one partial
hour file; the WAV header is finalized when the workflow stops.

The recording protocol uses 10-ms capture buffers and rotates WAV files every
60 minutes. Those behavioral choices live in
`protocols/recording.toml`, not in the rig file.

## Detect songs

Song detection has one protocol and one workflow. Two complete TOML profiles
change only how much data is saved:

| Profile | Raw WAV | `blocks.csv` | `events.csv` |
| --- | --- | --- | --- |
| `debug` | yes | yes | yes |
| `standard` | no | no | yes |

Use `debug` while inspecting and tuning the detector:

```powershell
python -m steg_song check song_detection --profile debug --rig config/rig.local.toml
python -m steg_song run song_detection --profile debug --rig config/rig.local.toml --session mouse-001-detection
```

While Bonsai runs, the same command window prints each confirmed song,
completed song and rejected candidate. It includes the event time, acoustic
onset or offset, span and occupancy. `events.csv` remains the complete
machine-readable record and is written without buffering so it can also be
read during the experiment.

Once the parameters are settled, use `--profile standard`. Standard is also the
default when `--profile` is omitted. Both profiles launch
`bonsai/protocols/song_detection.bonsai`; `save_raw_audio` and
`save_block_csv` are the only output gates.

Exact setup, signal processing and state semantics are documented in
`docs/song_detection.md` and `docs/rig_setup.md`.

## Trigger passive playback

The passive-playback protocol sends one command to the Arduino every 120
seconds. Avisoft owns the playlist and advances it in response to the hardware
TRG pulse; playlist paths do not belong in this repository.

```powershell
python -m steg_song check passive_playback --rig config/rig.local.toml
python -m steg_song run passive_playback --rig config/rig.local.toml --session passive-test
```

The first trigger occurs after one complete interval. Arduino responses appear
in the command window and are saved immediately to `playback_events.csv`.
Firmware, wiring and test instructions are in `docs/passive_playback.md`.

## Current scope

Recording, live song detection and fixed-interval passive playback triggering
are implemented. Song-triggered and combined playback are not yet implemented.
