# Milestone 1: detect songs and record the evidence

Status: recorder implemented and short live rotation test passed, 2026-09-06. Next duplicate the recorder and extend it with detection, keeping an independently switchable raw-audio writing arm. Native Bonsai first; detection still needs verification in installed Bonsai 2.9.1. See [recording guide](recording.md) and [reference review](references.md).

## Deliverable

An annotated `detect-song.bonsai` workflow that acquires the AudioMoth, displays its filtered energy and detection state, records raw audio, and logs one confirmation and one completion event per accepted song. Playback remains outside this milestone except for calibration recordings at the intended speaker level.

Use named nested workflows for `BandEnergy`, `SongState`, and `Logging`. Keep one continuously running acquisition source at the top level, shared with subjects, following the official state-machine tutorial. Do not reopen the microphone for each candidate/song.

## 1. Collect animal recordings on the rig PC

The standalone recorder and short development-PC checks are complete. Use [record-audio.bonsai](../bonsai/record-audio.bonsai) for the next step:

1. Select the rig's AudioMoth and session output path, following the [recording guide](recording.md).
2. Start with 250000 Hz, low-medium gain, and otherwise default device settings. Record placement and gain in session notes; keep them fixed within each comparison recording.
3. Record representative subject songs and background/cage noise. Include playback alone and subject singing during playback when available, at the intended speaker level.
4. Inspect these WAVs to choose gain and initial detector parameters. Check clipping, quiet terminal notes, spectrum, and continuity. A WAV header alone does not prove native-rate capture or absence of upstream resampling.

Checkpoint: a readable native-rate WAV and documented device/settings. If AudioMoth Live works but Bonsai cannot acquire, investigate the device/backend difference before building more logic.

## 2. Produce an interpretable energy trace

Proposed native path:

```text
AudioCapture
  -> ConvertScale (floating point; scale PCM16 by 1/32768)
  -> FrequencyFilter (HighPass, cutoff 20000 Hz, sample rate 250000)
  -> Norm (L2)
  -> Divide (sqrt(buffer sample count): 50 for 2500 samples)
  -> GreaterThan (fixed calibrated RMS threshold)
```

`Norm(L2) / sqrt(N)` computes RMS without a custom script. Normalize with the actual buffer length; if buffers change, update the normalization and all time/count conversions together. Preserve filter state between buffers. Use native `FrequencyFilter`; record its final kernel length and measure its contribution to timing. The [pipeline explanation](audio-pipeline.md) describes each operator's input and output.

Use linear full-scale RMS for the first threshold/CSV; dB conversion is optional. Do not threshold signed waveform samples or normalize each block independently. Start with one threshold; add hysteresis only if the traces show a need. Inspect built-in visualizers for raw waveform, RMS, threshold result, and state.

Checkpoint: playback-only audio stays below threshold while representative subject notes cross it. A threshold that loses quiet terminal notes can bias the offset even if it detects every song.

## 3. Define and implement song state

Use the official native state-machine pattern (`SelectMany`, `Condition`, `Take`, subjects, and `Repeat`) for three named states. Use synchronous `Scan` and arithmetic/comparison nodes for counters where needed; no asynchronous work inside `Scan`. These are candidate operator compositions, not a claim of a ready-made published song detector.

| State | Behavior |
| --- | --- |
| Idle | First above-threshold block starts a candidate; remember its start sample. |
| Candidate | Accumulate above-threshold audio duration, track the most recent active block, and tolerate gaps shorter than 200 ms. |
| Song | Emit confirmation once; continue tracking the last active block until 200 ms of quiet audio, then emit completion and return to Idle. |

Provisional confirmation criteria, revised toward the user's preference for fewer false positives: **at least 250 ms total above-threshold audio and at least 1 second from first active-block start to latest active-block end**. Evaluate confirmation on active blocks only. This permits pulsed notes and rejects a short isolated blip followed by silence. A candidate that reaches 200 ms of silence first is rejected and reset. These are starting settings to tune, not calibrated values or note classification. Estimated onset still refers to the candidate's beginning.

The agreed end rule is **20 consecutive below-threshold 10-ms blocks**. Reset the quiet count on every active block. Evaluate completion on newly received audio, not on a free-running timer: a stalled stream is not acoustic silence. `BufferCount(Count=20, Skip=1)` is a documented alternative for inspecting the recent quiet window; a synchronous resettable counter may be clearer in the state workflow. Do not put `DistinctUntilChanged` before counting quiet blocks. Use it only on state/condition transitions to suppress duplicate events.

`Throttle(200 ms)` was reviewed because it is explicitly documented for silence between events. It is not the primary end detector here: notification silence can also mean delayed audio delivery, and unpaced file replay changes its behavior. Counting audio blocks gives live and file inputs the same end rule.

Remember the estimated onset before confirmation. Estimated offset is the end of the last active block; completion time is separate. Initial resolution is 10 ms plus filter/envelope bias. Capture interruption or stopping mid-song must be logged as incomplete, not ordinary completion; restart with clean state.

Checkpoint: one confirmation/completion pair per accepted song, no completion between notes with gaps below 200 ms, and no duplicate completion during prolonged silence.

## 4. Log enough to diagnose the detector

Keep native `CsvWriter` logging and one raw `AudioWriter` branch. Use `ElementIndex`/sample counts for audio positions, and record software notification timestamps separately. Do not call these DAQ/session-synchronized times.

Run outputs:

- Timestamped raw WAVs: retain the standalone recorder's hourly splitting in a separate, switchable branch.
- `energy.csv`: block index, start/end sample, RMS, above-threshold flag, and buffer-received timestamp.
- `events.csv`: candidate/song ID, event type (`confirmed`, `completed`, `rejected`, or `incomplete`), onset/offset sample where available, decision sample, and notification timestamp.
- Saved workflow/configuration plus `run-notes.md`: gain, threshold, filter, confirmation criteria, software/package versions, mic/speaker placement, and calibration results. Manual notes are sufficient initially.

Use the event log to retain confirmation before the song ends; a per-song summary can be derived afterward. Keep any wall-clock timestamp explicitly labeled as software receipt time. Hardware synchronization of microphone events is future work.

## 5. Validate before calling the milestone complete

First feed known block/activity sequences through the native state logic: short blip, valid pulsed song, 190/200/210-ms quiet gaps, prolonged silence, back-to-back songs, and stop/restart. Then replace acquisition with `AudioReader` feeding the same detector and compare CSVs with manual review of real recordings. Count-based decisions should agree under unpaced replay; software timestamps need not.

Record missed songs, false detections, onset/offset errors, confirmation delay, premature splits, and effects of playback. Inspect disagreements with offline annotations rather than requiring identical behavior to the offline detector. Finish with a 10-minute live run including logging, checking for stalls and unexpected state transitions. Document observed performance; acceptance rates must come from representative recordings rather than an invented accuracy promise.

If one native subworkflow becomes difficult to understand or cannot pass these checks, identify that specific part before replacing it with a small C# operator. Do not introduce a custom detector class preemptively.

## Timing carried forward to milestone 2

For estimated last-note offset `t`, completion becomes available after `t + 0.200 s` of acquired audio; desired acoustic playback onset is `t + 0.300 s`. The nominal remaining budget is only **100 ms**, reduced by capture/delivery/processing and playback-start latency. Do not implement this as another 300-ms delay after completion. Measure the full path before claiming the target is achieved. The >=100-ms TRG pulse width is a separate hardware requirement, not necessarily a 100-ms delay before playback starts.
