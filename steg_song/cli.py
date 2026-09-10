from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Sequence

from .config import (
    ConfigError,
    ProtocolRun,
    RecordingRun,
    SongDetectionRun,
    load_run,
    validate_session_id,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        run = load_run(
            REPO_ROOT,
            args.rig.resolve(),
            args.protocol,
            args.profile,
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
        "protocol",
        choices=("recording", "song_detection"),
    )
    parser.add_argument(
        "--profile",
        choices=("standard", "debug"),
        help="song-detection config profile (default: standard)",
    )
    parser.add_argument("--rig", type=Path, required=True, help="path to rig TOML")


def _run_bonsai(run: ProtocolRun, session_id: str, headless: bool) -> int:
    session_dir = run.session_root / session_id
    if session_dir.exists():
        raise ConfigError(f"Session directory already exists: {session_dir}")
    session_dir.mkdir(parents=True)

    command = _bonsai_command(run, session_dir, headless)
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
    _write_json(manifest_path, manifest)

    try:
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
        manifest["exit_code"] = completed.returncode
        manifest["status"] = "completed" if completed.returncode == 0 else "failed"
        return completed.returncode
    except BaseException:
        manifest["status"] = "interrupted"
        raise
    finally:
        _remove_disabled_outputs(run, session_dir)
        manifest["finished_utc"] = _utc_now()
        _write_json(manifest_path, manifest)


def _bonsai_command(run: ProtocolRun, session_dir: Path, headless: bool) -> list[str]:
    command = [str(run.bonsai_executable), str(run.workflow)]
    command.append("--no-editor" if headless else "--start")
    properties = {
        "AudioDevice": run.audio_device,
        "AudioSampleRate": run.sample_rate_hz,
        "AudioSampleFormat": run.sample_format,
        "AudioBufferMs": run.buffer_ms,
    }
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
    for name, value in properties.items():
        command.extend(("-p", f"{name}={value}"))
    return command


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
