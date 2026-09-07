# steg-song-bot

Closed-loop song playback for *Scotinomys teguina*, starting with an AudioMoth USB microphone, Windows/Bonsai, Arduino, and Avisoft UltraSoundGate Player 116H.

## Agreed behavior

- Listen continuously, including during playback. Use the subject/playback amplitude difference rather than playback masking.
- Declare song completion after **200 ms of below-threshold audio**.
- Target playback onset **300 ms after estimated song offset**, not 300 ms after the completion notification.
- Eventually combine occasional playback with one probabilistic response decision per detected song and configurable onset/offset timing.
- Apply a shared **15-second minimum interval between issued playback triggers**; drop blocked requests rather than queue them.
- Reuse the WAVs, note-LSB encoding, and selected playlist order from `xmz_behavior_code`. Bonsai will control playback timing.
- Prefer established native Bonsai operators and annotated nested workflows. Use a small C# extension only if the native composition becomes cumbersome.

## Milestones

1. Audio capture, song detection, live inspection, and CSV/WAV logging.
2. Dry-run playback decisions, then Arduino/116H triggering and measured timing validation.
3. Optional future playback stack, such as a Windows-controlled Raspberry Pi endpoint, after verifying its acoustic bandwidth and synchronization.

Current status: the [song detector](bonsai/detect-song.bonsai) uses native comparisons, counters and conditional branches, with editable properties for threshold, minimum span, occupancy and silence timeout. It records energy/events CSV and optional hourly raw audio. Live and replay share the same detector components. Starting threshold: **0.01**. Output triggering is not implemented.

## Start recording on the rig PC

1. Use Bonsai 2.9.1 with the Audio, Core, and System packages at 2.9.1; install their dependencies through Bonsai's package manager.
2. Open `bonsai/record-audio.bonsai` and select that PC's AudioMoth in `AudioCapture.DeviceName`.
3. Inside `WriteWav`, set `AudioWriter.FileName` to a new session directory on the recording disk. Keep 250000 Hz, Mono16, 10-ms buffers, and `WindowCount.Count=360000`.
4. Start, inspect the waveform, and stop normally to finalize the last WAV. Budget about 1.8 GB per hour.

Current starting configuration: **250 kHz, medium gain, low gain mode enabled, physical switch at CUSTOM**, as reported from the rig. Keep gain and placement documented per session. AudioMoth is the detector input; faithful audio recording is handled separately with Avisoft.

- [Concrete first-milestone plan](docs/milestone-1.md)
- [Run and configure song detection](docs/detection.md)
- [Run the simple recorder](docs/recording.md)
- [Detection pipeline: inputs and outputs](docs/audio-pipeline.md)
- [Hardware/software setup record](docs/setup.md)
- [Official examples and community evidence](docs/references.md)

The default `recordings/` output directory is ignored by Git; external session storage is preferable for experiments. Exploratory analyses, plots and example-specific results stay in ignored `scratch/`. The generic state tests use Python only to exercise native Bonsai workflows. The standalone recorder remains available unchanged for simple acquisition.
