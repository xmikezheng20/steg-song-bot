from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess
import threading
from typing import Sequence, TextIO

from .config import (
    CombinedPlaybackRun,
    ConfigError,
    PassivePlaybackRun,
    ProtocolRun,
    RecordingRun,
    SongDetectionRun,
    load_run,
    validate_session_id,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        run = load_run(
            args.rig.resolve(),
            args.config.resolve(),
        )
        if args.command == "check":
            print(json.dumps(run.as_dict(), indent=2))
            return 0
        return _run_bonsai(run, validate_session_id(args.session), args.headless)
    except ConfigError as error:
        parser.error(str(error))
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m steg_song")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="validate and resolve a protocol")
    _common_arguments(check)

    run = commands.add_parser("run", help="create a session and launch Bonsai")
    _common_arguments(run)
    run.add_argument("--session", required=True, help="new session-directory name")
    run.add_argument("--headless", action="store_true", help="run without the Bonsai editor")
    return parser


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="path to a complete protocol TOML",
    )
    parser.add_argument("--rig", type=Path, required=True, help="path to rig TOML")


def _run_bonsai(
    run: ProtocolRun | PassivePlaybackRun,
    session_id: str,
    headless: bool,
) -> int:
    session_dir = run.session_root / session_id
    if session_dir.exists():
        raise ConfigError(f"Session directory already exists: {session_dir}")
    session_dir.mkdir(parents=True)

    random_seed = (
        secrets.randbelow(2_147_483_646) + 1
        if isinstance(run, CombinedPlaybackRun)
        else None
    )
    command = _bonsai_command(run, session_dir, headless, random_seed)
    manifest_path = session_dir / "run.json"
    manifest = {
        "status": "starting",
        "started_utc": _utc_now(),
        "finished_utc": None,
        "exit_code": None,
        "resolved_config": run.as_dict(),
        "session": {"id": session_id, "directory": str(session_dir.resolve())},
        "command": command,
    }
    if random_seed is not None:
        manifest["scheduler_random_seed"] = random_seed
    _write_json(manifest_path, manifest)

    monitor_stop: threading.Event | None = None
    monitor_thread: threading.Thread | None = None
    playback_event_path: Path | None = None
    if isinstance(run, SongDetectionRun):
        event_path = session_dir / "events.csv"
        print(f"Live song events will appear here. Full log: {event_path.resolve()}")
        monitor_stop = threading.Event()
        monitor_thread = threading.Thread(
            target=_monitor_events,
            args=(event_path, run.buffer_ms / 1000, monitor_stop),
            daemon=True,
        )
        monitor_thread.start()
    if isinstance(run, (PassivePlaybackRun, CombinedPlaybackRun)):
        playback_event_path = session_dir / "playback_events.csv"
        if isinstance(run, CombinedPlaybackRun):
            message = "Live playback decisions and Arduino responses"
        else:
            message = "Live Arduino responses"
        print(
            f"{message} will appear below. "
            f"Full log: {playback_event_path.resolve()}"
        )

    try:
        exit_code = _run_process(command, playback_event_path)
        manifest["exit_code"] = exit_code
        if exit_code == 130:
            manifest["status"] = "interrupted"
        else:
            manifest["status"] = "completed" if exit_code == 0 else "failed"
        return exit_code
    except BaseException:
        manifest["status"] = "interrupted"
        raise
    finally:
        if monitor_stop is not None and monitor_thread is not None:
            monitor_stop.set()
            monitor_thread.join(timeout=2)
        _remove_disabled_outputs(run, session_dir)
        manifest["finished_utc"] = _utc_now()
        _write_json(manifest_path, manifest)


def _bonsai_command(
    run: ProtocolRun | PassivePlaybackRun,
    session_dir: Path,
    headless: bool,
    random_seed: int | None = None,
) -> list[str]:
    command = [str(run.bonsai_executable), str(run.workflow)]
    command.append("--no-editor" if headless else "--start")
    if headless:
        command.append("--no-boot")
    properties: dict[str, object] = {}
    if isinstance(run, ProtocolRun):
        properties.update(
            {
                "AudioDevice": run.audio_device,
                "AudioSampleRate": run.sample_rate_hz,
                "AudioSampleFormat": run.sample_format,
                "AudioBufferMs": run.buffer_ms,
            }
        )
    if isinstance(run, (RecordingRun, SongDetectionRun)):
        properties.update(
            {
                "WavFileBlocks": run.blocks_per_wav,
                "WavOutputFile": str((session_dir / "audio.wav").resolve()),
                "WavSampleRate": run.sample_rate_hz,
            }
        )
    if isinstance(run, SongDetectionRun):
        properties.update(
            {
                "SaveRawAudio": str(run.save_raw_audio).lower(),
                "SaveBlockCsv": str(run.save_block_csv).lower(),
                "FilterSampleRate": run.sample_rate_hz,
                "HighPassCutoffHz": run.high_pass_hz,
                "HighPassKernelLength": run.high_pass_kernel_length,
                "RmsDivisor": run.rms_divisor,
                "RmsThreshold": run.rms_threshold,
                "MinimumSpanBlocks": run.minimum_span_blocks,
                "MinimumOccupancy": run.minimum_occupancy,
                "EndSilenceBlocks": run.end_silence_blocks,
                "BlockLogFile": str((session_dir / "blocks.csv").resolve()),
                "EventLogFile": str((session_dir / "events.csv").resolve()),
            }
        )
    if isinstance(run, PassivePlaybackRun):
        properties.update(
            {
                "ArduinoPort": run.serial_port,
                "ArduinoBaudRate": run.serial_baud_rate,
            }
        )
        properties["PlaybackInterval"] = _format_bonsai_timespan(
            run.interval_seconds
        )
    if isinstance(run, CombinedPlaybackRun):
        if random_seed is None:
            raise ValueError("combined playback requires a scheduler random seed")
        properties.update(
            {
                "PassiveIntervalBlocks": run.passive_interval_blocks,
                "SongTriggerDelayBlocks": run.song_trigger_delay_blocks,
                "SongTriggerProbability": run.song_trigger_probability,
                "TriggerLockoutBlocks": run.trigger_lockout_blocks,
                "SchedulerRandomSeed": random_seed,
                "EnableSongTriggered": str(run.enable_song_triggered).lower(),
                "EnablePassive": str(run.enable_passive).lower(),
                "ArduinoPort": run.serial_port,
                "ArduinoBaudRate": run.serial_baud_rate,
            }
        )
    for name, value in properties.items():
        command.extend(("-p", f"{name}={value}"))
    return command


def _run_process(
    command: list[str], playback_event_path: Path | None
) -> int:
    process: subprocess.Popen[str] | None = None
    event_file: TextIO | None = None
    event_writer = None
    workflow_error = False
    try:
        if playback_event_path is not None:
            event_file = playback_event_path.open(
                "w", newline="", encoding="utf-8"
            )
            event_writer = csv.writer(event_file)
            event_writer.writerow(("ProcessedUtc", "Event"))
            event_file.flush()

        process = subprocess.Popen(
            command,
            cwd=Path(command[1]).parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            message = line.rstrip("\r\n")
            if message.startswith("[playback] ") and event_writer is not None:
                event_writer.writerow((_utc_now(), message.removeprefix("[playback] ")))
                event_file.flush()
            if "Runtime exception stack trace" in message:
                workflow_error = True
        exit_code = process.wait()
        return 1 if workflow_error and exit_code == 0 else exit_code
    except KeyboardInterrupt:
        _stop_process(process)
        return 130
    except BaseException:
        _stop_process(process)
        raise
    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()
        if event_file is not None:
            event_file.close()


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _remove_disabled_outputs(run: ProtocolRun, session_dir: Path) -> None:
    if not isinstance(run, SongDetectionRun):
        return
    if not run.save_block_csv:
        (session_dir / "blocks.csv").unlink(missing_ok=True)
    if not run.save_raw_audio:
        for path in session_dir.glob("audio*.wav"):
            path.unlink()


def _monitor_events(
    path: Path,
    block_seconds: float,
    stop: threading.Event,
) -> None:
    seen: set[tuple[str, str, str]] = set()
    while not stop.is_set():
        _print_new_events(path, block_seconds, seen)
        stop.wait(0.25)
    _print_new_events(path, block_seconds, seen)


def _print_new_events(
    path: Path,
    block_seconds: float,
    seen: set[tuple[str, str, str]],
) -> None:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error):
        return

    for row in rows:
        key = (
            row.get("Event", ""),
            row.get("CandidateId", ""),
            row.get("BlockIndex", ""),
        )
        if not key[0] or not key[2] or key in seen:
            continue
        try:
            message = _format_live_event(row, block_seconds)
        except (KeyError, TypeError, ValueError):
            continue
        seen.add(key)
        print(message, flush=True)


def _format_live_event(row: dict[str, str], block_seconds: float) -> str:
    event = row["Event"].lower()
    decision = (int(row["BlockIndex"]) + 1) * block_seconds
    if event not in {"confirmed", "completed", "rejected"}:
        return f"[event] {event.upper()}  time={_format_elapsed(decision)}"

    candidate = int(row["CandidateId"])
    onset = int(row["OnsetBlock"]) * block_seconds
    occupancy = float(row["Occupancy"])

    if event == "confirmed":
        return (
            f"[song {candidate}] CONFIRMED  onset={_format_elapsed(onset)}  "
            f"confirmed={_format_elapsed(decision)}  occupancy={occupancy:.1%}"
        )

    offset = int(row["OffsetBlock"]) * block_seconds
    span = offset - onset
    if event == "completed":
        return (
            f"[song {candidate}] COMPLETED  onset={_format_elapsed(onset)}  "
            f"offset={_format_elapsed(offset)}  span={span:.2f}s  "
            f"occupancy={occupancy:.1%}"
        )
    if event == "rejected":
        return (
            f"[candidate {candidate}] REJECTED  onset={_format_elapsed(onset)}  "
            f"offset={_format_elapsed(offset)}  span={span:.2f}s  "
            f"occupancy={occupancy:.1%}"
        )
    raise ValueError(f"Unsupported detector event: {event}")


def _format_elapsed(seconds: float) -> str:
    minutes, remainder = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remainder:05.2f}"
    return f"{minutes:02d}:{remainder:05.2f}"


def _format_bonsai_timespan(seconds: int) -> str:
    days, remainder = divmod(seconds, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    clock = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{days}.{clock}" if days else clock


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
