# Milestone 1: song detection and logging

Status: native detector implemented in Bonsai 2.9.1. See the [run guide](detection.md) for configuration and repeatable checks. Exploratory recordings, plots and parameter sweeps belong in ignored scratch storage, not permanent documentation.

## Implemented

- `detect-song.bonsai`: one continuous AudioCapture, shared native band-energy and song-state workflows, energy/events CSV, and a switchable hourly raw-WAV arm.
- `replay-detection.bonsai`: native AudioReader driven by Range for unpaced replay through exactly the same detector and logging workflows.
- `BandEnergy.bonsai`: PCM16 to F32, 20-kHz high pass, L2 norm divided by 50 for 2500-sample/10-ms buffers.
- `SongState.bonsai`: native threshold, synchronous Scan, arithmetic, comparisons and conditional branches. Four exposed properties; no logic or parameters embedded in expressions.
- `LogDetection.bonsai`: per-block evidence, one confirmation/completion per accepted song, rejected candidates, and terminal status on source completion.

## Current rules

| Setting | Start value |
| --- | --- |
| Filter | HighPass, 20000 Hz, sample rate 250000, KernelLength 60 |
| RMS threshold | 0.01, fixed full-scale reference |
| Minimum candidate span | 100 blocks = 1 second |
| Minimum occupancy | 0.2 |
| Silence timeout | 20 blocks = 200 ms |

A candidate begins at its first active block. On active blocks, calculate span from candidate start through the latest active block end, and occupancy as active blocks / span blocks. Confirm once when **span >= minimum span AND occupancy >= minimum occupancy**. The required active duration therefore scales with span; there is no independent minimum-active-time setting. This replaces the earlier 250-ms accumulated-activity proposal.

Continue a confirmed song even if occupancy subsequently falls. After 20 consecutive inactive blocks, emit completion for a confirmed song or rejection for an unconfirmed candidate, then reset. Estimated offset is the last active block end, not the completion position. No completion is inferred from a stalled stream. Source completion while active is incomplete; toolbar Stop cancels subscriptions, so missing terminal records/unmatched events must be treated as interrupted (see the run guide).

## Next rig check

1. Keep gain and geometry fixed within each comparison recording.
2. Record several subject songs, background/cage noise, and playback when available. Keep raw recording enabled and review events alongside the audio.
3. Review missed or extra events, premature splits, and quiet first/final notes against these WAVs. Adjust the single RMS threshold first; preserve the conservative span/occupancy rule unless evidence warrants a change.
4. Run a longer rig session and inspect block counts, logs, and WAVs. Development-PC tests do not establish rig sensitivity, specificity, or hardware latency.

The goal is reliable detection. AudioMoth distortion matters only insofar as it changes detections or timing; the faithful audio recording is a separate Avisoft acquisition.

## Timing carried forward to milestone 2

For estimated offset `t`, completion is available after `t + 0.200 s` of acquired audio; desired acoustic playback onset is `t + 0.300 s`. Only 100 ms nominally remains for capture delivery, processing and playback latency. Do not add another 300-ms delay after completion. Later add occasional/probabilistic scheduling, the shared 15-second trigger interval, and Arduino/116H output, then measure the acoustic result and DAQ timing. This milestone sends no output commands.
