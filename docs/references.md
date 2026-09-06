# Source review

Reviewed 2026-09-06. These sources justify the building blocks and workflow style. No complete, maintainer-validated AudioMoth singing-mouse detector was found in this review; our song criteria and composition require testing.

| Source | What we will adapt / limitation |
| --- | --- |
| [Official Acquisition and Tracking tutorial](https://bonsai-rx.org/docs/tutorials/acquisition.html) | `AudioCapture -> AudioWriter`, matching sample rates, reading WAVs, and `CsvWriter`. It does not verify 250-kHz AudioMoth capture on this PC. |
| [Official Closed-Loop tutorial](https://bonsai-rx.org/docs/tutorials/closed-loop.html) | Scalar thresholding, `DistinctUntilChanged` for transitions, and measured loop latency. Its examples are not acoustic song classification. |
| [Official State Machines tutorial](https://bonsai-rx.org/docs/tutorials/state-machines.html) | Top-level hardware connections, subjects, named states with `SelectMany`, conditions, one-shot `Take`, repetition, and independent event logging. Primary design pattern for this project. |
| [Official Scan documentation](https://bonsai-rx.org/docs/articles/reactive-scan.html) | Native nested accumulation for resettable counters; follow its recommendation to keep accumulation synchronous. |
| [Official BufferCount documentation](https://bonsai-rx.org/docs/api/Bonsai.Reactive.BufferCount.html) | Counted and overlapping windows of input notifications. Supports audio-block-based timing without relying on wall-clock arrival intervals. |
| [Official Throttle documentation](https://bonsai-rx.org/docs/articles/reactive-throttle.html) | Emits after a quiet interval between notifications; the wait necessarily delays detection. Reviewed, but pure notification silence is insufficient evidence of acoustic silence. |
| [Official Norm API](https://bonsai-rx.org/docs/api/Bonsai.Dsp.Norm.html), [FrequencyFilter API](https://bonsai-rx.org/docs/api/Bonsai.Dsp.FrequencyFilter.html) | Native building blocks for the proposed filtered RMS path. RMS normalization is our mathematical composition, not a published song-detection recipe. |
| [Google Group: play sound while a condition holds, 2021](https://groups.google.com/g/bonsai-users/c/i_4wM-qigPY) | Bruno Cruz demonstrates `GreaterThan` and `DistinctUntilChanged` to drive state changes; user reports success. Goncalo Lopes explains threshold property externalization. Reuse the event pattern, not that playback backend. |
| [Google Group: ultrasonic microphone not detected, 2021](https://groups.google.com/g/bonsai-users/c/n9olY3-I4IA) | Reports of working ultrasonic USB acquisition alongside enumeration difficulties; Goncalo Lopes discusses backend differences. Relevant acquisition troubleshooting, not proof of AudioMoth compatibility. |
| [Google Group: audio/video timestamps, 2021](https://groups.google.com/g/bonsai-users/c/_ZAKxBot3iw) | Audio-buffer notification jitter and Goncalo Lopes's `WithLatestFrom` guidance. Supports distinguishing audio samples from software arrival times; does not supply hardware synchronization for this rig. |
| [GitHub Discussion #2508: realtime stimulation graph, 2026](https://github.com/orgs/bonsai-rx/discussions/2508) | A supplied workflow is revised after inspection: software pulse timing/plots differ from hardware behavior; recommend hardware pulse generation and hardware timestamps. Apply this to milestone-2 Arduino timing and DAQ validation. The thread is not marked as an accepted answer. |

Prefer these maintained operators and documented patterns over an unverified third-party extension. Preserve exact tested package versions and document any deviation when implementing.
