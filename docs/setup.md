# Rig setup record

Updated 2026-09-06. Development-PC capture is verified; rig-PC settings must be checked on that machine. No firmware, application settings, or wiring were changed by the agent.

## AudioMoth

Roles: **AudioMoth Flash App** installs USB-microphone firmware if needed; **AudioMoth USB Microphone App** configures it; **AudioMoth Live App** provides an independent capture/spectrogram check; **Bonsai** acquires the experiment stream.

Manufacturer procedure: use USB/OFF for configuration. DEFAULT exposes the selected rate/gain; CUSTOM additionally applies configured filters/advanced settings. Latest user-reported rig configuration: **250 kHz, medium gain, low gain mode enabled, CUSTOM switch position**. This supersedes the original low-medium/default starting configuration. The current Bonsai recorder applies no filtering. Record any device filter settings separately; CUSTOM alone does not specify them. [Official instructions](https://www.openacousticdevices.info/usb-microphone).

Record together when connecting:

| Item | Current knowledge / action |
| --- | --- |
| Firmware | User reports USB-microphone firmware already configured; record actual version, do not reflash by default. |
| Rate | User configured 250000 Hz; live Bonsai capture at that rate succeeded after cable replacement. |
| Gain / mic placement | Medium gain with low gain mode enabled, user-reported. Placement still to document; keep gain and geometry fixed within a comparison recording. |
| Switch / device filters | CUSTOM, user-reported. Device filter settings and firmware version still to record. No settings changed by the agent. |
| Windows input | Confirm enumeration, microphone access, and available format. Record any gain/enhancement settings; disable automatic level processing if present. |
| Bonsai device | On the development PC, Windows lists `Microphone (250kHz AudioMoth USB Microphone)`, status OK. OpenAL selector `Microphone (250kHz AudioMoth US` successfully captured audio. Reselect the device on the rig PC. |

Bonsai capture has now been verified directly with a short rotation test and a one-minute recording; AudioMoth Live remains an optional independent diagnostic and was not run by the agent. Stop other microphone capture applications before testing Bonsai to avoid device-sharing ambiguity. Select the exact input in Bonsai, use Mono16/250000 Hz/10 ms, and verify a WAV. Do not assume successful capture in another application proves Bonsai capture works: the older user group documents backend-specific ultrasonic-microphone enumeration issues ([case study](https://groups.google.com/g/bonsai-users/c/n9olY3-I4IA)).

## Bonsai

Tested recorder: Bonsai 2.9.1, with Audio/Core/System 2.9.1 and their package-manager dependencies. Typical installation path is `%LOCALAPPDATA%\Bonsai`. No scripting package or custom extension is needed. The workflow in this repository is the current recording baseline.

For the detector, additionally install **Bonsai.Dsp 2.9.1** and **Bonsai.Scripting.Expressions 2.9.0** with their dependencies. Expressions only label output fields; no custom C# extension or external process is used. Native visualizers suffice. Acquisition remains at the top level and all four detector settings are exposed on the SongState node. See the [detector run guide](detection.md).

## Avisoft Player 116H — prepare for milestone 2

RECORDER USGH remains the playback application. Proposed checklist, to verify together on the rig:

- Select the Player 116H and use file-header playback rate with its required real-time oversampling configuration. Retain the existing proven LSB-compatible playback settings and verify DOUT after any change.
- Reuse PCM16 stimulus WAVs with notes encoded low in the LSB; do not normalize/re-encode the prepared files.
- Load the selected stimulus order with paths valid on the playback PC. The example text playlist contains Linux paths and timetable entries; prepare an order-only import or verify their handling with timetable disabled.
- Enable **stop after each file**; disable timetable, randomize, automatic echo, and playlist delay for externally controlled sequential playback. Explicitly choose stop versus loop at list end and verify the first selected entry.
- Select the documented external trigger source, **joystick b2** (some versions label it **b2|b6**), and verify one trigger advances one entry. Record the actual UI labels/version.
- Record speaker model, supply, analog volume, software volume, microphone geometry, and any playback transformations. Compare playback-only and subject amplitudes at these settings.

TRG is internally pulled up and activated by pulling it to ground for **at least 100 ms**. Plan a transistor/open-collector interface, with exact pinout and board confirmed before wiring. DOUT carries the WAV's note LSB and goes to the DAQ. It is not a continuously asserted playback-busy signal. Sources: [116H manual](https://www.avisoft.com/usgmanual_player116h.pdf), [playlist settings](https://www.avisoft.com/Help/RECORDER/playlist.htm), [playback settings](https://www.avisoft.com/Help/RECORDER/playback_settings.htm).

## Arduino / DAQ — pending

Arduino is not needed for the recorder. Confirm the rig's serial port, board identity, pin assignment, electrical interface, DAQ input channel/levels, and shared grounding when implementing output. Firmware will create pulse width locally and acknowledge commands. Measure command/trigger-to-DOUT latency and verify the acoustic onset separately; software receipt timestamps are not hardware timestamps.

Update this record with verified rig settings as each stage is implemented.
