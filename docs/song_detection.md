# Song detection

There is one song-detection protocol and one Bonsai workflow. The `debug` and
`standard` TOML files contain the complete configuration; they differ only in
two output switches.

| Profile | Raw WAV | Every block | Events |
| --- | --- | --- | --- |
| `debug` | yes | `blocks.csv` | `events.csv` |
| `standard` | no | no | `events.csv` |

Use `debug` for detector development and auditing, then `standard` for runs
where only event timing is needed. Both launch
`bonsai/protocols/song_detection.bonsai`. The launcher maps
`save_raw_audio` and `save_block_csv` directly to two simple workflow gates;
event logging is always on.

## Band energy

Each 10-ms Mono16 block is converted to full-scale floating point, high-pass
filtered at 20 kHz, and reduced to RMS. A block is active only when
`Rms > rms_threshold`; equality is quiet.

## State transition

`SongState` stores the current candidate's onset block, last active-block end,
active-block count, candidate number and confirmation status. For every block it
performs four steps:

1. **Advance:** increment the block index and decide whether the previous
   candidate is still open.
2. **UpdateCandidate:** start a candidate on the first active block or update
   its counters.
3. **Decide:** test confirmation and the end-of-song silence timeout.
4. **Emit:** publish the new state and at most one event.

A candidate is confirmed when its active-to-active span is at least
`minimum_span_ms` and its active-block fraction is at least
`minimum_occupancy`. Confirmation is not later revoked. A candidate ends after
`end_silence_ms` since its last active block. It emits `completed` if confirmed
and `rejected` otherwise.

With the current 10-ms blocks, the defaults resolve to a 150-block minimum span
and 25 quiet blocks. Exactly 250 ms of quiet ends the candidate. `OffsetBlock`
is the half-open end of the last active block, not the later decision block.

## Output

Every run creates `events.csv` and `run.json`. The debug profile also creates
timestamped `audio*.wav` files and `blocks.csv`.

The launcher watches `events.csv` and prints concise live messages in the
command window for confirmed, completed and rejected events. For example:

```text
[song 1] CONFIRMED  onset=00:34.06  confirmed=00:35.56  occupancy=50.7%
[song 1] COMPLETED  onset=00:34.06  offset=00:39.74  span=5.68s  occupancy=55.5%
```

This monitor is always active for song detection and is identical in the
standard and debug profiles. The CSV remains authoritative; the terminal text
is only a convenient live view.

`ProcessedUtc` is a software processing timestamp. Use block positions—not that
timestamp—for acoustic timing.

The default threshold is a starting value, not a calibrated biological
criterion. Tune it from labeled recordings while keeping the filter, buffer
size and microphone configuration fixed.
