# Combined playback

`combined_playback` runs the existing song detector and one playback scheduler.
The scheduler sends accepted triggers to the same Arduino/Avisoft path used by
the passive-playback hardware test. It does not select or play audio files.

## Configuration

The standard and debug TOML files contain the same detector and scheduler
settings. They differ only in diagnostic output:

| Profile | Raw WAV | `blocks.csv` | `events.csv` | `playback_events.csv` |
| --- | --- | --- | --- | --- |
| `debug` | yes | yes | yes | yes |
| `standard` | no | no | yes | yes |

These repository files are templates. A copied TOML can live anywhere and is
selected directly with `--config`; its workflow is resolved through the
repository root in `rig.local.toml`.

The scheduler defaults are:

```toml
[playback]
enable_song_triggered = true
enable_passive = true
passive_interval_seconds = 120
song_trigger_delay_ms = 50
song_trigger_probability = 0.60
trigger_lockout_seconds = 12
```

All scheduler timing is converted to 10-ms audio blocks by the launcher. The
serial port and baud rate remain rig-specific settings in
`config/rig.local.toml`.

## Scheduler rules

Each audio block advances one scheduler clock. The rules are applied in this
order:

1. A confirmed detector `completed` event schedules one song attempt 50 ms
   later. Completion already follows the detector's 250-ms end-silence rule, so
   the attempt is normally about 300 ms after the last active audio block.
2. Passive attempts occur at 120, 240, 360 seconds, and so on. A skipped passive
   attempt does not shift this clock.
3. An attempt is locked out when it is less than 12 seconds after the previous
   accepted trigger. Exactly 12.00 seconds is allowed. The reference is the
   playback trigger/start, not the end of the audio file.
4. An eligible song attempt draws once against the configured probability.
   Locked attempts do not consume a random draw.
5. If song and passive attempts coincide, a successful song draw wins. If the
   song draw fails, the passive attempt may trigger. At most one trigger is sent
   in any audio block.

Skipped attempts are discarded, not queued. Detection is never paused or
masked during playback or lockout.

The same workflow supports song-triggered-only playback. Its template sets
`enable_song_triggered = true` and `enable_passive = false`, so no passive
attempts are scheduled. Probability applies only to song-triggered attempts.
Setting the switches the other way runs fixed passive playback while retaining
audio recording and detection. Disabling both is rejected as a configuration
error.

## Audit trail

The launcher creates these files in every session:

- `run.json`: fully resolved configuration, command and per-session random seed;
- `events.csv`: detector events;
- `playback_events.csv`: every trigger/skip decision and Arduino response.

Decision lines include the trigger source, audio block, song candidate and
completion block when relevant, probability draw, collision state, skip reason,
and blocks since the previous accepted trigger. They also appear immediately in
the command window during a run.

## Test

First confirm the AudioMoth and Arduino settings:

```powershell
conda activate audiomoth
python -m steg_song check --config protocols/combined_playback.debug.toml --rig config/rig.local.toml
```

Then configure Avisoft as for passive playback: external trigger enabled, stop
after each item enabled, and playlist looping enabled so Avisoft remains ready
for the next trigger. Start a short debug session:

```powershell
python -m steg_song run --config protocols/combined_playback.debug.toml --rig config/rig.local.toml --session combined-test-01
```

During the run, verify passive and song decisions in the command window. After
stopping Bonsai, compare `events.csv`, `playback_events.csv`, the debug WAV and
`blocks.csv`. Use a new session name for every run; the launcher will not
overwrite an existing session directory.
