# Run the song detector

## Install and open

Use Bonsai 2.9.1 with **Audio, Core, DSP and System 2.9.1**, plus **Bonsai.Scripting.Expressions 2.9.0**, and their package-manager dependencies. All operators come from these packages; no custom C# extension, .NET SDK, or Python installation is needed to run detection.

Open [detect-song.bonsai](../bonsai/detect-song.bonsai). Keep its neighboring `.bonsai` files together: included workflows share the same detector between live capture and replay.

```text
AudioCapture -> BandEnergy -> SongState -> LogDetection
     |
     +-> RecordRawAudio -> WindowCount -> WriteWav
```

Before each run:

1. Select the rig AudioMoth in AudioCapture. Keep 250000 Hz, Mono16 and 10-ms buffers. Current reported device settings: medium gain, low gain mode enabled, CUSTOM.
2. Select the **SongState node** and edit its four exposed properties in Bonsai's property grid. No expression editing is needed. Stop before changing settings; each run starts with fresh counters.
3. In `LogDetection`, set both CsvWriter paths to `energy.csv` and `events.csv` in a new session folder. Inside `WriteWav`, set AudioWriter to `audio.wav` in that same folder. Timestamp suffixes prevent accidental reuse; recording paths are relative to the top-level workflow directory. The defaults write to the repository's ignored `recordings/` folder.
4. Keep `RecordRawAudio` enabled for testing. Inside it, Boolean `Value=true` passes audio to the writer; `false` disables that arm while detection/CSV continue. Change this **before starting**, not during a session. Hourly splitting is still 360000 buffers.
5. Save the workflow/settings used for the run and note microphone/speaker placement. Start and inspect `BandEnergy` RMS, `SongState` output and the CSV files. Stop other microphone applications before acquisition.

## Settings

| SongState property | Default | Meaning |
| --- | ---: | --- |
| Threshold | **0.01** | Fixed full-scale RMS; native GreaterThan operand. |
| MinSpanBlocks | 100 | Minimum span of 1 second; native GreaterThanOrEqual operand. |
| MinOccupancy | 0.2 | Minimum active/span fraction; native Divide and GreaterThanOrEqual. |
| QuietBlocks | 20 | Finish after 200 ms of acquired silence; native counter comparison. |

`MinSpanBlocks=100` means 1 second; `QuietBlocks=20` means 200 ms. Use positive integer block counts and occupancy greater than zero and at most one. RMS threshold must be finite and positive. Occupancy includes inter-note gaps but excludes the final silence timeout. It is tested when confirming, not used to revoke an already confirmed song. Keep the 2500-sample block size: filtering, normalization, timing and log sample positions assume it.

Inside Scan, **UpdateCandidate** updates onset, latest active block, candidate ID and active count with native Add, comparisons and conditional branches. **ConfirmSong** divides active count by span, compares both criteria, and combines the Boolean results. **QuietExpired** counts acquired silence. The **Event** branches choose confirmation, completion or rejection. Each conditional group uses native Condition and Merge; counters and decisions run synchronously on each block. There is no detection suppression during playback or cooldown.

Only field-labeling expressions remain: they assign readable names to records and CSV columns. They contain no arithmetic, decisions, or configurable parameters. The operational logic is in the visible graph, following the [native Condition pattern](https://bonsai-rx.org/docs/tutorials/state-machines.html) and [synchronous Scan guidance](https://bonsai-rx.org/docs/articles/reactive-scan.html).

The detector graph is shared between live and replay. Property overrides on a SongState include node belong to that calling workflow; use the same four values in live and replay when comparing results. Editing an underlying operator changes the shared default. Save both the calling workflow and any modified included files.

## What is logged

Both CSVs use the same columns; energy contains every block, events contains transitions and a terminal record when the source completes.

| Column | Meaning |
| --- | --- |
| BlockIndex, StartSample, EndSample | Zero-based audio index and half-open sample interval; EndSample / 250000 is the decision position in acquired audio. |
| Rms, Active | Filtered full-scale RMS and strict `Rms > Threshold` result. |
| State | Idle, Candidate or Song after processing the block. A completion/rejection row is Idle but retains the just-finished candidate's measurements. |
| CandidateId | Incrementing ID per candidate, including rejected candidates; starts fresh each run. |
| OnsetSample, OffsetSample | Candidate's first active-block start and latest active-block end; -1 when no candidate. Offset is provisional until completion. |
| SpanSeconds, Occupancy | Active-to-active span and active blocks divided by that span, excluding trailing quiet time. |
| Event | `confirmed`, `completed`, `rejected`, `stream_end`, `incomplete`, or empty in ordinary energy rows. |
| ProcessedUtc | UTC software processing timestamp, recorded after state calculation. Not an acoustic timestamp or DAQ synchronization. |

On normal source completion (e.g. replay EOF), the final state produces `stream_end` if idle, or `incomplete` if still in a candidate/song. **Toolbar Stop unsubscribes** rather than completing the source, so it need not emit a terminal event. Treat an absent terminal record as an interrupted run, and an open candidate or unmatched confirmation as incomplete. Never convert these into ordinary song completions. The last energy rows retain the state needed for review. A crash or forced termination can also leave unwritten output; stop normally to dispose the writers.

CSV timestamps from fast replay reflect processing time. Use sample positions to compare recordings and detector timing. A rotated raw file contains consecutive acquired audio, not a new detector state; state continues across file rotation.

## Replay a WAV

Open [replay-detection.bonsai](../bonsai/replay-detection.bonsai), set AudioReader.FileName and the log output paths. Input must be mono PCM16 at 250000 Hz. The default `../recordings/input.wav` is a placeholder: choose your recording before running. No microphone or playback device is opened by this workflow.

Range drives AudioReader as fast as processing permits; it stops when the WAV's complete buffers are exhausted. An unconnected AudioReader would pace playback in wall-clock time. AudioReader discards a final incomplete 2500-sample block. A candidate still open at EOF remains incomplete.

Replay and live use identical BandEnergy, SongState and LogDetection files. Only the audio source and optional raw recording differ.

## Repeat the state checks

Python is only a convenience for generating test inputs and checking CSVs:

```powershell
python scripts/validate_detector.py --bonsai "$env:LOCALAPPDATA/Bonsai/Bonsai.exe"
```

This stdlib-only runner launches finite native Bonsai workflows without hardware, checks actual events and block indices, and verifies the exposed properties. Cases cover threshold equality, blips, minimum span, occupancy boundaries, 190/200/210-ms silence gaps, reset and incomplete streams. Test output and example-specific comparisons stay under ignored `scratch/`.
