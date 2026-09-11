import csv
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree

from steg_song.config import (
    CombinedPlaybackRun,
    ConfigError,
    PassivePlaybackRun,
    SongDetectionRun,
    load_combined_playback_run,
    load_passive_playback_run,
    load_recording_run,
    load_run,
    load_song_detection_run,
    validate_session_id,
)
from steg_song.cli import (
    _bonsai_command,
    _format_live_event,
    _remove_disabled_outputs,
    _run_process,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_NAMESPACE = "https://bonsai-rx.org/2018/workflow"
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


class ConfigTests(unittest.TestCase):
    def test_combined_playback_resolves_one_scheduler(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bonsai = root / "Bonsai.exe"
            bonsai.touch()
            rig = root / "rig.toml"
            rig.write_text(
                f'''[bonsai]
executable = "{bonsai.as_posix()}"
[audio_input]
device_name = "AudioMoth"
sample_rate_hz = 250000
sample_format = "Mono16"
gain = "medium"
low_gain_mode = true
switch_position = "CUSTOM"
[arduino_trigger]
port = "COM3"
baud_rate = 9600
[storage]
session_root = "{(root / 'sessions').as_posix()}"
''',
                encoding="utf-8",
            )

            run = load_combined_playback_run(REPO_ROOT, rig, "standard")

            self.assertIsInstance(run, CombinedPlaybackRun)
            self.assertEqual(run.passive_interval_blocks, 12000)
            self.assertEqual(run.song_trigger_delay_blocks, 5)
            self.assertEqual(run.song_trigger_probability, 0.8)
            self.assertEqual(run.trigger_lockout_blocks, 1200)
            command = " ".join(
                _bonsai_command(
                    run, root / "run", headless=True, random_seed=12345
                )
            )
            self.assertIn("PassiveIntervalBlocks=12000", command)
            self.assertIn("SongTriggerDelayBlocks=5", command)
            self.assertIn("SongTriggerProbability=0.8", command)
            self.assertIn("TriggerLockoutBlocks=1200", command)
            self.assertIn("SchedulerRandomSeed=12345", command)
            self.assertIn("ArduinoPort=COM3", command)
            self.assertIn("AudioDevice=AudioMoth", command)

    def test_passive_playback_uses_only_trigger_hardware(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bonsai = root / "Bonsai.exe"
            bonsai.touch()
            rig = root / "rig.toml"
            rig.write_text(
                f'''[bonsai]
executable = "{bonsai.as_posix()}"
[arduino_trigger]
port = "COM3"
baud_rate = 9600
[storage]
session_root = "{(root / 'sessions').as_posix()}"
''',
                encoding="utf-8",
            )

            run = load_passive_playback_run(REPO_ROOT, rig)

            self.assertIsInstance(run, PassivePlaybackRun)
            self.assertEqual(run.serial_port, "COM3")
            self.assertEqual(run.serial_baud_rate, 9600)
            self.assertEqual(run.interval_seconds, 120)

            command = " ".join(
                _bonsai_command(run, root / "run", headless=True)
            )
            self.assertIn("ArduinoPort=COM3", command)
            self.assertIn("ArduinoBaudRate=9600", command)
            self.assertIn("PlaybackInterval=00:02:00", command)
            self.assertIn("--no-boot", command)
            self.assertNotIn("AudioDevice=", command)

    def test_passive_playback_output_is_flushed_to_csv(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "emit_event.py"
            script.write_text(
                'print("[playback] START", flush=True)\n'
                'print("[playback] DONE", flush=True)\n',
                encoding="utf-8",
            )
            event_log = root / "playback_events.csv"

            exit_code = _run_process(
                [sys.executable, str(script)], event_log
            )

            self.assertEqual(exit_code, 0)
            with event_log.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["Event"] for row in rows], ["START", "DONE"])
            self.assertTrue(all(row["ProcessedUtc"] for row in rows))

    def test_recording_protocol_derives_block_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bonsai = root / "Bonsai.exe"
            bonsai.touch()
            rig = root / "rig.toml"
            rig.write_text(
                f'''[bonsai]
executable = "{bonsai.as_posix()}"
[audio_input]
device_name = "AudioMoth"
sample_rate_hz = 250000
sample_format = "Mono16"
gain = "medium"
low_gain_mode = true
switch_position = "CUSTOM"
[storage]
session_root = "{(root / 'sessions').as_posix()}"
''',
                encoding="utf-8",
            )

            run = load_recording_run(REPO_ROOT, rig, "recording")

            self.assertEqual(run.samples_per_block, 2500)
            self.assertEqual(run.blocks_per_wav, 360000)
            self.assertEqual(run.wav_split_minutes, 60)

    def test_session_id_rejects_paths(self) -> None:
        with self.assertRaises(ConfigError):
            validate_session_id("../existing")

    def test_live_event_messages_are_concise(self) -> None:
        confirmed = {
            "BlockIndex": "3555",
            "CandidateId": "1",
            "OnsetBlock": "3406",
            "OffsetBlock": "3556",
            "Occupancy": "0.5066666667",
            "Event": "confirmed",
        }
        completed = {
            "BlockIndex": "3998",
            "CandidateId": "1",
            "OnsetBlock": "3406",
            "OffsetBlock": "3974",
            "Occupancy": "0.5545774648",
            "Event": "completed",
        }

        self.assertEqual(
            _format_live_event(confirmed, 0.01),
            "[song 1] CONFIRMED  onset=00:34.06  confirmed=00:35.56  "
            "occupancy=50.7%",
        )
        self.assertEqual(
            _format_live_event(completed, 0.01),
            "[song 1] COMPLETED  onset=00:34.06  offset=00:39.74  "
            "span=5.68s  occupancy=55.5%",
        )

    def test_song_detection_profiles_derive_the_same_detector_settings(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bonsai = root / "Bonsai.exe"
            bonsai.touch()
            rig = root / "rig.toml"
            rig.write_text(
                f'''[bonsai]
executable = "{bonsai.as_posix()}"
[audio_input]
device_name = "AudioMoth"
sample_rate_hz = 250000
sample_format = "Mono16"
gain = "medium"
low_gain_mode = true
switch_position = "CUSTOM"
[storage]
session_root = "{(root / 'sessions').as_posix()}"
''',
                encoding="utf-8",
            )

            debug = load_song_detection_run(REPO_ROOT, rig, "debug")
            standard = load_song_detection_run(REPO_ROOT, rig, "standard")

            self.assertIsInstance(debug, SongDetectionRun)
            self.assertIsInstance(standard, SongDetectionRun)
            self.assertEqual(debug.workflow, standard.workflow)
            self.assertEqual(debug.minimum_span_blocks, 150)
            self.assertEqual(standard.minimum_span_blocks, 150)
            self.assertEqual(debug.end_silence_blocks, 25)
            self.assertEqual(standard.end_silence_blocks, 25)
            self.assertEqual(debug.rms_divisor, 50)
            self.assertEqual(debug.blocks_per_wav, 360000)
            self.assertEqual(debug.audiomoth_gain, "medium")
            self.assertTrue(debug.low_gain_mode)
            self.assertTrue(debug.save_raw_audio)
            self.assertTrue(debug.save_block_csv)
            self.assertFalse(standard.save_raw_audio)
            self.assertFalse(standard.save_block_csv)

            debug_command = " ".join(
                _bonsai_command(debug, root / "debug", headless=True)
            )
            standard_command = " ".join(
                _bonsai_command(standard, root / "standard", headless=True)
            )
            for command in (debug_command, standard_command):
                self.assertIn("WavOutputFile=", command)
                self.assertIn("BlockLogFile=", command)
                self.assertIn("EventLogFile=", command)
            self.assertIn("SaveRawAudio=true", debug_command)
            self.assertIn("SaveBlockCsv=true", debug_command)
            self.assertIn("SaveRawAudio=false", standard_command)
            self.assertIn("SaveBlockCsv=false", standard_command)

            default = load_run(REPO_ROOT, rig, "song_detection")
            self.assertIsInstance(default, SongDetectionRun)
            self.assertEqual(default.profile_name, "standard")

            output = root / "standard"
            output.mkdir()
            for name in ("blocks.csv", "audio.wav", "events.csv"):
                (output / name).touch()
            _remove_disabled_outputs(standard, output)
            self.assertFalse((output / "blocks.csv").exists())
            self.assertFalse((output / "audio.wav").exists())
            self.assertTrue((output / "events.csv").exists())


class BonsaiWorkflowTests(unittest.TestCase):
    def test_nested_property_mappings_resolve(self) -> None:
        for path in (REPO_ROOT / "bonsai").rglob("*.bonsai"):
            if path.is_file():
                workflow = ElementTree.parse(path).getroot().find(
                    f"{{{WORKFLOW_NAMESPACE}}}Workflow"
                )
                self._check_workflow(workflow, path)

    def _check_workflow(
        self, workflow: ElementTree.Element, source_path: Path
    ) -> None:
        nodes = list(workflow.find(f"{{{WORKFLOW_NAMESPACE}}}Nodes"))
        edges = list(workflow.find(f"{{{WORKFLOW_NAMESPACE}}}Edges"))

        for index, node in enumerate(nodes):
            nested = node.find(f"{{{WORKFLOW_NAMESPACE}}}Workflow")
            if nested is not None:
                self._check_workflow(nested, source_path)

            if node.get(XSI_TYPE) != "ExternalizedMapping":
                continue
            mapping = node.find(f"{{{WORKFLOW_NAMESPACE}}}Property")
            for edge in edges:
                if int(edge.get("From")) != index:
                    continue
                target = nodes[int(edge.get("To"))]
                target_workflow = target.find(
                    f"{{{WORKFLOW_NAMESPACE}}}Workflow"
                )
                if target.get(XSI_TYPE) == "IncludeWorkflow":
                    included = (source_path.parent / target.get("Path")).resolve()
                    target_workflow = ElementTree.parse(included).getroot().find(
                        f"{{{WORKFLOW_NAMESPACE}}}Workflow"
                    )
                if target_workflow is None:
                    continue
                exposed = {
                    item.find(f"{{{WORKFLOW_NAMESPACE}}}Property").get("DisplayName")
                    for item in target_workflow.find(
                        f"{{{WORKFLOW_NAMESPACE}}}Nodes"
                    )
                    if item.get(XSI_TYPE) == "ExternalizedMapping"
                }
                self.assertIn(
                    mapping.get("Name"),
                    exposed,
                    f"{source_path}: {mapping.get('DisplayName')} targets a missing "
                    f"nested property {mapping.get('Name')}",
                )


if __name__ == "__main__":
    unittest.main()
