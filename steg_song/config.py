from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import tomllib
from typing import Any


class ConfigError(ValueError):
    """Raised when rig or protocol configuration is invalid."""


@dataclass(frozen=True)
class ProtocolRun:
    protocol_name: str
    workflow: Path
    bonsai_executable: Path
    audio_device: str
    sample_rate_hz: int
    sample_format: str
    audiomoth_gain: str
    low_gain_mode: bool
    switch_position: str
    buffer_ms: int
    session_root: Path
    samples_per_block: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": {
                "name": self.protocol_name,
                "workflow": str(self.workflow),
            },
            "bonsai": {"executable": str(self.bonsai_executable)},
            "audio_input": {
                "device_name": self.audio_device,
                "sample_rate_hz": self.sample_rate_hz,
                "sample_format": self.sample_format,
                "gain": self.audiomoth_gain,
                "low_gain_mode": self.low_gain_mode,
                "switch_position": self.switch_position,
            },
            "acquisition": {
                "buffer_ms": self.buffer_ms,
                "samples_per_block": self.samples_per_block,
            },
            "storage": {"session_root": str(self.session_root)},
        }


@dataclass(frozen=True)
class RecordingRun(ProtocolRun):
    wav_split_minutes: int
    blocks_per_wav: int

    def as_dict(self) -> dict[str, Any]:
        result = super().as_dict()
        result["recording"] = {
            "wav_split_minutes": self.wav_split_minutes,
            "blocks_per_wav": self.blocks_per_wav,
        }
        return result


@dataclass(frozen=True)
class SongDetectionRun(ProtocolRun):
    profile_name: str
    save_raw_audio: bool
    save_block_csv: bool
    wav_split_minutes: int
    blocks_per_wav: int
    high_pass_hz: int
    high_pass_kernel_length: int
    rms_threshold: float
    minimum_span_ms: int
    minimum_occupancy: float
    end_silence_ms: int
    minimum_span_blocks: int
    end_silence_blocks: int
    rms_divisor: float

    def as_dict(self) -> dict[str, Any]:
        result = super().as_dict()
        result["protocol"]["profile"] = self.profile_name
        result["signal_processing"] = {
            "high_pass_hz": self.high_pass_hz,
            "high_pass_kernel_length": self.high_pass_kernel_length,
            "rms_divisor": self.rms_divisor,
        }
        result["song_detection"] = {
            "rms_threshold": self.rms_threshold,
            "minimum_span_ms": self.minimum_span_ms,
            "minimum_span_blocks": self.minimum_span_blocks,
            "minimum_occupancy": self.minimum_occupancy,
            "end_silence_ms": self.end_silence_ms,
            "end_silence_blocks": self.end_silence_blocks,
        }
        result["output"] = {
            "save_raw_audio": self.save_raw_audio,
            "save_block_csv": self.save_block_csv,
            "save_events_csv": True,
            "wav_split_minutes": self.wav_split_minutes,
            "blocks_per_wav": self.blocks_per_wav,
        }
        return result


def load_run(
    repo_root: Path,
    rig_path: Path,
    protocol_name: str,
    profile_name: str | None = None,
) -> ProtocolRun:
    if protocol_name == "recording":
        if profile_name is not None:
            raise ConfigError("recording does not use a profile")
        return load_recording_run(repo_root, rig_path, protocol_name)
    if protocol_name == "song_detection":
        return load_song_detection_run(
            repo_root, rig_path, profile_name or "standard"
        )
    raise ConfigError(f"Unknown protocol: {protocol_name!r}")


def load_recording_run(
    repo_root: Path, rig_path: Path, protocol_name: str
) -> RecordingRun:
    protocol = _read_protocol(repo_root, protocol_name)
    base = _load_common_settings(repo_root, rig_path, protocol_name, protocol)
    split_minutes, blocks_per_wav = _recording_settings(protocol, base.buffer_ms)
    return RecordingRun(
        **base.__dict__,
        wav_split_minutes=split_minutes,
        blocks_per_wav=blocks_per_wav,
    )


def load_song_detection_run(
    repo_root: Path, rig_path: Path, profile_name: str
) -> SongDetectionRun:
    if profile_name not in {"debug", "standard"}:
        raise ConfigError(f"Unknown song-detection profile: {profile_name!r}")
    protocol = _read_toml(
        repo_root / "protocols" / f"song_detection.{profile_name}.toml"
    )
    declared_profile = _required(protocol, "protocol", "profile", str)
    if declared_profile != profile_name:
        raise ConfigError(
            f"Profile file {profile_name!r} declares {declared_profile!r}"
        )
    base = _load_common_settings(
        repo_root, rig_path, "song_detection", protocol
    )
    if base.sample_format != "Mono16":
        raise ConfigError("song detection requires audio_input.sample_format = \"Mono16\"")

    high_pass_hz = _positive_int(protocol, "signal_processing", "high_pass_hz")
    kernel_length = _positive_int(
        protocol, "signal_processing", "high_pass_kernel_length"
    )
    threshold = _positive_number(protocol, "song_detection", "rms_threshold")
    minimum_span_ms = _positive_int(
        protocol, "song_detection", "minimum_span_ms"
    )
    occupancy = _positive_number(
        protocol, "song_detection", "minimum_occupancy"
    )
    end_silence_ms = _positive_int(
        protocol, "song_detection", "end_silence_ms"
    )

    if high_pass_hz >= base.sample_rate_hz / 2:
        raise ConfigError("signal_processing.high_pass_hz must be below Nyquist")
    if occupancy > 1:
        raise ConfigError("song_detection.minimum_occupancy must be at most 1")
    if minimum_span_ms % base.buffer_ms:
        raise ConfigError("song_detection.minimum_span_ms must contain whole blocks")
    if end_silence_ms % base.buffer_ms:
        raise ConfigError("song_detection.end_silence_ms must contain whole blocks")

    split_minutes, blocks_per_wav = _recording_settings(
        protocol, base.buffer_ms, section="output"
    )
    return SongDetectionRun(
        **base.__dict__,
        wav_split_minutes=split_minutes,
        blocks_per_wav=blocks_per_wav,
        profile_name=profile_name,
        save_raw_audio=_required(
            protocol, "output", "save_raw_audio", bool
        ),
        save_block_csv=_required(
            protocol, "output", "save_block_csv", bool
        ),
        high_pass_hz=high_pass_hz,
        high_pass_kernel_length=kernel_length,
        rms_threshold=threshold,
        minimum_span_ms=minimum_span_ms,
        minimum_occupancy=occupancy,
        end_silence_ms=end_silence_ms,
        minimum_span_blocks=minimum_span_ms // base.buffer_ms,
        end_silence_blocks=end_silence_ms // base.buffer_ms,
        rms_divisor=math.sqrt(base.samples_per_block),
    )


def validate_session_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ConfigError(
            "Session ID must start with a letter or digit and contain only letters, "
            "digits, dots, underscores or hyphens"
        )
    return value


def _read_protocol(repo_root: Path, protocol_name: str) -> dict[str, Any]:
    return _read_toml(repo_root / "protocols" / f"{protocol_name}.toml")


def _load_common_settings(
    repo_root: Path,
    rig_path: Path,
    protocol_name: str,
    protocol: dict[str, Any],
) -> ProtocolRun:
    rig = _read_toml(rig_path)
    name = _required(protocol, "protocol", "name", str)
    if name != protocol_name:
        raise ConfigError(
            f"Protocol file {protocol_name!r} declares the name {name!r}"
        )

    workflow = repo_root / _required(protocol, "protocol", "workflow", str)
    bonsai = Path(_required(rig, "bonsai", "executable", str)).expanduser()
    session_root = Path(_required(rig, "storage", "session_root", str)).expanduser()
    sample_rate = _positive_int(rig, "audio_input", "sample_rate_hz")
    sample_format = _required(rig, "audio_input", "sample_format", str)
    audiomoth_gain = _required(rig, "audio_input", "gain", str)
    low_gain_mode = _required(rig, "audio_input", "low_gain_mode", bool)
    switch_position = _required(rig, "audio_input", "switch_position", str)
    device = _required(rig, "audio_input", "device_name", str)
    buffer_ms = _positive_int(protocol, "acquisition", "buffer_ms")

    samples_numerator = sample_rate * buffer_ms
    if samples_numerator % 1000:
        raise ConfigError("sample_rate_hz * buffer_ms must produce whole samples")
    samples_per_block = samples_numerator // 1000

    if not device.strip():
        raise ConfigError("audio_input.device_name cannot be empty")
    if not audiomoth_gain.strip():
        raise ConfigError("audio_input.gain cannot be empty")
    if switch_position not in {"USB/OFF", "DEFAULT", "CUSTOM"}:
        raise ConfigError(
            "audio_input.switch_position must be USB/OFF, DEFAULT or CUSTOM"
        )
    if sample_format not in {"Mono8", "Mono16", "Stereo8", "Stereo16"}:
        raise ConfigError(f"Unsupported AudioCapture sample format: {sample_format!r}")
    if not workflow.is_file():
        raise ConfigError(f"Workflow does not exist: {workflow}")
    if not bonsai.is_file():
        raise ConfigError(f"Bonsai executable does not exist: {bonsai}")

    return ProtocolRun(
        protocol_name=name,
        workflow=workflow.resolve(),
        bonsai_executable=bonsai.resolve(),
        audio_device=device,
        sample_rate_hz=sample_rate,
        sample_format=sample_format,
        audiomoth_gain=audiomoth_gain,
        low_gain_mode=low_gain_mode,
        switch_position=switch_position,
        buffer_ms=buffer_ms,
        session_root=session_root.resolve(),
        samples_per_block=samples_per_block,
    )


def _recording_settings(
    protocol: dict[str, Any],
    buffer_ms: int,
    section: str = "recording",
) -> tuple[int, int]:
    split_minutes = _positive_int(protocol, section, "wav_split_minutes")
    wav_milliseconds = split_minutes * 60 * 1000
    if wav_milliseconds % buffer_ms:
        raise ConfigError("wav_split_minutes must contain whole acquisition blocks")
    return split_minutes, wav_milliseconds // buffer_ms


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as error:
        raise ConfigError(f"Configuration file does not exist: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Invalid TOML in {path}: {error}") from error


def _required(data: dict[str, Any], section: str, key: str, expected: type) -> Any:
    try:
        value = data[section][key]
    except (KeyError, TypeError) as error:
        raise ConfigError(f"Missing required setting: {section}.{key}") from error
    if type(value) is not expected:
        raise ConfigError(f"{section}.{key} must be {expected.__name__}")
    return value


def _positive_int(data: dict[str, Any], section: str, key: str) -> int:
    value = _required(data, section, key, int)
    if value <= 0:
        raise ConfigError(f"{section}.{key} must be positive")
    return value


def _positive_number(data: dict[str, Any], section: str, key: str) -> float:
    try:
        value = data[section][key]
    except (KeyError, TypeError) as error:
        raise ConfigError(f"Missing required setting: {section}.{key}") from error
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{section}.{key} must be a number")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{section}.{key} must be finite and positive")
    return value
