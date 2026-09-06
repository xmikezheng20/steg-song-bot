# Simple hourly recorder

Open `bonsai/record-audio.bonsai` in the installed Bonsai 2.9.1. This workflow uses native modules only and records raw, unfiltered audio.

Tested direct dependencies: Bonsai.Audio, Bonsai.Core, and Bonsai.System **2.9.1**, with their package-manager dependencies. The detection-stage DSP package is not required for this recorder. Bonsai's generated `.bonsai/` directories and visualizer layouts are local state and are ignored by Git.

```text
AudioCapture -> WindowCount -> WriteWav (SelectMany)
                                 Source1 -> AudioWriter -> Output
```

## Run

From the repository root in PowerShell:

```powershell
& "$env:LOCALAPPDATA\Bonsai\Bonsai.exe" ".\bonsai\record-audio.bonsai"
```

1. Select `AudioCapture`. The current OpenAL device selector is `Microphone (250kHz AudioMoth US` (the truncated name works on this PC). If moving computers, select the AudioMoth from the device list rather than guessing its string.
2. Keep `SampleRate=250000`, `SampleFormat=Mono16`, and `BufferLength=10` ms. User's AudioMoth configuration: low-medium gain, 250 kHz, otherwise defaults.
3. Double-click `WriteWav`, select `AudioWriter`, and set `FileName` to the desired session's base WAV path. Default `../recordings/audio.wav` resolves relative to the workflow directory. Prefer a new session directory on the recording disk for experiments.
4. Start the workflow. Double-click `AudioCapture` to inspect the incoming waveform if desired. Stop normally to finish the last WAV header.

On the rig PC, first make a short recording and confirm it produces a readable WAV before a longer animal session. Leave gain fixed within each comparison recording; if adjusting it, start a separate recording and note the new setting. Record microphone distance/placement and speaker level if playback is present. These notes are the inputs for the next detection/calibration stage.

Each full file contains 360000 blocks x 2500 samples = 900000000 samples = 3600 seconds, about 1.8 GB (1.68 GiB). The final file can be shorter. `WindowCount` streams each block as it arrives; it does not accumulate an hour in memory. Leave `Skip` unset for adjacent, non-overlapping files.

`WriteWav` opens one `AudioWriter` per window; the microphone remains open across file changes. `Suffix=Timestamp` produces names such as `audio2026-09-06T15_10_43.wav`. These name suffixes are file-creation times, not DAQ synchronization timestamps. `Overwrite=false` prevents replacement of existing files. `Buffered=true` queues disk writes on a separate thread.

### How WindowCount and SelectMany work together

`AudioCapture` emits one block every 10 ms of acquired audio. `WindowCount` turns that single stream into a sequence of smaller streams: window 1 receives the first 360000 blocks, window 2 receives the next 360000, and so on. It exposes each window when it begins, so downstream nodes process its blocks immediately.

`WriteWav` is our descriptive name for a native `SelectMany` node. For each incoming window, `SelectMany` runs its nested workflow with that window's audio stream as `Source1`. The nested `AudioWriter` starts a new timestamped WAV on its first block, appends subsequent blocks, and finalizes the file when the window completes. The next window gets a new writer subscription and file. Stopping normally also disposes the current writer and finalizes its partial file.

In general, `SelectMany` combines the outputs of these nested workflow executions into one output stream. Here its useful side effect is giving each window its own file-writer lifetime. The nested `WorkflowOutput` passes audio onward; it does not write another file. `AudioCapture` stays outside the nested workflow, so file rotation does not restart the microphone.

To shorten the split interval, set `WindowCount.Count = seconds x 100` (e.g. 6000 for one minute) while keeping 10-ms capture buffers. Changing buffer length also changes the number of blocks per hour; update both together. No filter, normalization, or threshold is applied to the saved PCM samples.

## Development sequence

Keep this recorder as a simple standalone baseline. Next duplicate it as a detection workflow, retaining a separate, switchable raw-recording arm for testing. Detection runs continuously across file boundaries; energy/event logging belongs to separate branches.

The [milestone plan](milestone-1.md) records the proposed conservative confirmation criteria and the agreed 200-ms song-end silence. None of these detector settings affect this raw recorder.

## Validation

2026-09-06: a live 5.5-second Bonsai test with two-second windows produced 2.0, 2.0, and 1.5-second mono PCM16 WAVs at 250000 Hz. Their concatenated PCM payload matched a simultaneously written continuous reference byte-for-byte. This checks capture and writer rotation, including the partial last file. An hour-long soak test has not been performed.

A subsequent 60-second live run produced exactly 15000000 samples (30000044-byte WAV including its header), no clipped PCM samples, and no entirely zero 10-ms blocks. The normal relative output path resolved to the repository's `recordings/` directory. This was a quiet-room capture, not a known ultrasonic calibration stimulus; it does not prove the frequency response or absence of upstream resampling.

The split-test WAVs remain local under ignored `scratch/recorder-test/`; the one-minute capture is under ignored `recordings/`. Temporary test workflows/logs were removed during the pre-commit audit. These local recordings are not included in a clone. Firmware and gain were not changed; the test processes finished.

Sources: official [acquisition example](https://bonsai-rx.org/docs/tutorials/acquisition.html), [WindowCount](https://bonsai-rx.org/docs/api/Bonsai.Reactive.WindowCount.html), [AudioWriter](https://bonsai-rx.org/docs/api/Bonsai.Audio.AudioWriter.html), and [CLI](https://bonsai-rx.org/docs/articles/cli.html). The file-window/writer combination was verified on the installed runtime.
