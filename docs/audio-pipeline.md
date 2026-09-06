# What each detection operator receives and produces

At 250000 samples/second and 10-ms capture buffers, each incoming item represents **2500 samples from one channel**. There are nominally 100 items per second; USB/Windows can deliver them with some timing jitter. The first three stages retain a waveform; the final three reduce each waveform block to a level and then a decision.

| Operator | Input | Output | Purpose |
| --- | --- | --- | --- |
| `AudioCapture` | AudioMoth USB microphone | A 1-row x 2500-column `Mat` of signed 16-bit integers for each 10 ms | Sample values range from -32768 to 32767. Rows are channels, columns are time samples. |
| `ConvertScale` | The PCM16 matrix | A same-sized floating-point matrix (`Depth=F32`, `Scale=0.000030517578125`, `Shift=0`) | Divide by 32768, giving a fixed full-scale reference, approximately -1 to +1. For example, 3277 becomes about 0.1000. This is unit conversion, not automatic gain control or per-buffer normalization. |
| `FrequencyFilter` | The floating-point waveform | A same-sized filtered waveform | With HighPass and cutoff 20000 Hz, attenuate low-frequency cage/room sound while retaining higher-frequency activity. Keep sample rate 250000 and filter state across blocks. The cutoff is a transition, not a brick wall, and filtering adds some delay. |
| `Norm`, type L2 | One filtered block `x[0] ... x[2499]` | One nonnegative scalar `sqrt(sum(x[i]^2))` | Combine both positive and negative waveform excursions into a measure of magnitude. L2 alone grows with the square root of block length. |
| `Divide`, value 50 | The scalar L2 norm | One scalar RMS: `sqrt(sum(x[i]^2)/2500)` | Since `sqrt(2500)=50`, this produces the block's RMS amplitude relative to full scale. It is an amplitude measure derived from mean-square energy, not calibrated sound pressure. |
| `GreaterThan` | The RMS scalar | One Boolean per block | `true` means the block is louder than the chosen threshold; `false` means it is not. This is activity evidence, not yet a song event. |

Example: if a filtered block has RMS 0.02, its L2 norm is 1.0. Dividing by 50 returns 0.02. A hypothetical threshold of 0.01 produces `true`. Those numbers illustrate the math, not a recommended detection threshold.

The next layer integrates the Boolean stream to reject isolated activity and recognize songs. Start conservatively, but remember the estimated onset before confirmation. Track song offset separately using 200 ms of quiet audio.

The raw WAV branch splits directly from `AudioCapture`, before `ConvertScale` and `FrequencyFilter`. This preserves the original PCM16 data for later analysis and lets us revise detection parameters without rerecording. The simple recorder does not yet include the detection chain described here.

References: [AudioCapture](https://bonsai-rx.org/docs/api/Bonsai.Audio.AudioCapture.html), [ConvertScale](https://bonsai-rx.org/docs/api/Bonsai.Dsp.ConvertScale.html), [FrequencyFilter](https://bonsai-rx.org/docs/api/Bonsai.Dsp.FrequencyFilter.html), [Norm](https://bonsai-rx.org/docs/api/Bonsai.Dsp.Norm.html).
