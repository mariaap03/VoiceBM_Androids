# ProcessingPipe - Audacity Audio Cleaning Pipeline

Batch audio denoising and enhancement pipeline that processes WAV files through Audacity via its scripting interface (`mod-script-pipe`).

The noise profile required by Audacity's Noise Reduction is captured **automatically** for each file: the pipeline uses [Respiro-EN](https://github.com/keums/respiro-en) to detect breath / silence regions in the audio, selects the best one, and feeds it to Audacity as the noise sample — no manual profile capture needed.

## Prerequisites

- **Audacity** with the `mod-script-pipe` module enabled
- **Python 3** (3.8+ recommended)
- **Respiro-EN** installed at the path configured in `denoisepipe.py` (see Setup)
- Python packages: `torch`, `torchaudio`, `librosa`, `numpy`, `intervaltree`
- Input audio files in `.wav` format

### Enabling mod-script-pipe in Audacity

1. Open Audacity
2. Go to **Edit > Preferences > Modules** (on Linux/Windows) or **Audacity > Preferences > Modules** (on macOS)
3. Set `mod-script-pipe` to **Enabled**
4. Restart Audacity

## Project Structure

```
ProcessingPipe/
├── denoisepipe.py          # Main Python script that drives the batch pipeline
├── AudacityMacros/
│   ├── Denoiseok.txt       # Denoising + enhancement macro (used by the pipeline)
│   └── Join.txt            # Track joining macro (utility, not used in main pipeline)
└── README.md
```

Respiro-EN lives outside this repository (see Setup).

## How It Works

The pipeline communicates with a running Audacity instance through named pipes. For each WAV file in the input directory, it:

1. Loads the file into Python and runs **Respiro-EN** to detect breath/silence intervals (non-speech regions that carry background noise)
2. Picks the **longest qualifying silence** as the noise sample source
3. Imports the audio into Audacity
4. Selects only the silence segment inside Audacity and runs **`GetNoiseProfile:`** — this stores a spectral fingerprint of the background noise in Audacity's memory
5. Selects the full track and applies the **`Denoiseok`** macro (stereo-to-mono, high-pass filter, noise reduction ×2 using the captured profile, noise gate, EQ curve, normalization)
6. Exports the processed audio as mono WAV to the output directory
7. Removes the track from Audacity to free memory

## Setup

### 1. Install Respiro-EN

Clone or download [Respiro-EN](https://github.com/keums/respiro-en) and place the `respiro-en.pt` model weights inside it.  Then open `denoisepipe.py` and update the `RESPIRO_PATH` constant at **line 21** to point to that directory:

```python
RESPIRO_PATH = "/path/to/Respiro-en"
```

Install the required Python packages if not already present:

```bash
pip install torch torchaudio librosa numpy intervaltree
```

### 2. Install the Audacity Macro

Copy `AudacityMacros/Denoiseok.txt` into your Audacity macros directory:

| OS | Macro directory |
|----|-----------------|
| Linux | `~/.audacity-data/Macros/` or `~/.config/audacity/Macros/` |
| macOS | `~/Library/Application Support/audacity/Macros/` |
| Windows | `%APPDATA%\audacity\Macros\` |

The file must be named exactly `Denoiseok.txt` to match the macro call in the script. If you rename it, update the corresponding line in `denoisepipe.py` (see Customizing Parameters).

### 3. Configure Input/Output Directories

Open `denoisepipe.py` and update the two directory constants:

```python
in_dir  = "/path/to/input/audio"
out_dir = "/path/to/output/audio"
```

- `in_dir` — directory containing the `.wav` files to process
- `out_dir` — directory where cleaned files will be saved (must already exist)

## Running the Pipeline

1. **Start Audacity** (it must be running before the script)
2. Run the script:

```bash
python denoisepipe.py
```

The script logs each file and the silence segment it selected for the noise profile. All output files keep their original filenames and are written to `out_dir` as mono WAV.

## Macro Reference

### Denoiseok.txt (Main Denoising Macro)

This macro applies seven sequential processing steps:

| Step | Effect | Key Parameters | Purpose |
|------|--------|---------------|---------|
| 1 | StereoToMono | `<Current Settings>` | Convert to single channel |
| 2 | High-Pass Filter | Frequency=90 Hz, Rolloff=12 dB/oct | Remove low-frequency rumble |
| 3 | Noise Reduction (pass 1) | `<Current Settings>` | Reduce background noise |
| 4 | Noise Gate | Threshold=-40 dB, Level-Reduction=-24 dB, Attack=10 ms, Decay=100 ms, Hold=50 ms | Gate out low-level noise in silent sections |
| 5 | Filter Curve (EQ) | 17-point B-spline curve, 67 Hz – 20.8 kHz | Shape frequency response for speech clarity |
| 6 | Noise Reduction (pass 2) | `<Current Settings>` | Second denoising pass |
| 7 | Normalize | Peak Level=-1 dB, Remove DC Offset=yes | Normalize volume, prevent clipping |

### What `<Current Settings>` means and how the pipeline sets it

In Audacity macro syntax, `Use_Preset="<Current Settings>"` tells an effect to apply using whatever state is currently held in Audacity's **in-memory** effect settings — it does not refer to any file or project-level configuration.

For `NoiseReduction` (Steps 3 and 6) the in-memory state has two independent components:

| Component | What it is | How it is set by the pipeline |
|-----------|-----------|-------------------------------|
| **Noise profile** | Spectral fingerprint of the background noise | `GetNoiseProfile:` is called on the silence segment found by Respiro-EN, once per file, before the macro runs |
| **Algorithm parameters** | Sensitivity, Frequency Smoothing, Time Smoothing sliders | Persist from the last time the Noise Reduction dialog was used; not changed by the pipeline — configure them once in Audacity if you need non-default values |

`StereoToMono` (Step 1) also carries `<Current Settings>` in the macro file, but that effect has no meaningful user-settable parameters, so it is a no-op in practice.

### Automatic noise profile capture (Respiro-EN)

For each file the pipeline calls `find_noise_profile_segment()`, which:

1. Runs `BreathDetector` (Respiro-EN) on the raw WAV file at a threshold of `0.064` and a minimum segment length of 20 frames (200 ms)
2. Picks the **longest detected interval** that is at least `MIN_SILENCE_DURATION` (default 0.3 s)
3. Returns `(start, end)` in seconds

In Audacity, the pipeline then runs:

```
SelectTime: Start=<start> End=<end>
GetNoiseProfile:
SelectAll:
Macro_Denoiseok:
```

`GetNoiseProfile:` is the scripting equivalent of **Effect > Noise Reduction > Get Noise Profile**. It stores the spectral fingerprint of the selected audio segment into Audacity's memory. Because this happens right before the macro, the `<Current Settings>` used by Steps 3 and 6 refer to this freshly captured, per-file profile.

**Fallback behaviour:** If Respiro-EN finds no silence that meets the minimum duration (or if detection fails), the pipeline falls back to the first 0.5 s of the file, which typically contains room tone before the speaker begins.

### Join.txt (Utility Macro)

Aligns multiple tracks end-to-end and mixes them into a single track. Not used by the main pipeline but available for concatenating audio files manually in Audacity.

## Customizing Parameters

### Changing the noise-profile detection settings

In `denoisepipe.py`:

| Constant / argument | Default | What it controls |
|---------------------|---------|-----------------|
| `RESPIRO_PATH` | (path to Respiro-en) | Location of the Respiro-EN directory |
| `MIN_SILENCE_DURATION` | `0.3` s | Shortest interval accepted as a noise sample; increase for a stricter selection |
| `threshold` in `find_noise_profile_segment` | `0.064` | Respiro-EN detection threshold — lower values detect more (possibly shorter) breath regions |
| `min_length` in `find_noise_profile_segment` | `20` frames (200 ms) | Minimum frame run that counts as a detected breath interval |

### Changing the Macro Name

If you rename `Denoiseok.txt` to something else (e.g., `MyMacro.txt`), update the corresponding call in `denoisepipe.py`:

```python
# Before
do_command("Macro_Denoiseok:")
# After
do_command("Macro_MyMacro:")
```

### Adjusting Audio Processing Parameters

Edit `AudacityMacros/Denoiseok.txt` directly. Each line is one effect with its parameters. Key values you may want to tweak:

| Parameter | Location | Default | What it controls |
|-----------|----------|---------|-----------------|
| High-pass frequency | Line 2, `FREQUENCY` | `90` Hz | Cutoff for low-frequency removal. Raise to cut more bass, lower to keep more. |
| High-pass rolloff | Line 2, `ROLLOFF` | `dB12` | Steepness of the filter. Options: `dB6`, `dB12`, `dB24`, `dB36`, `dB48`. |
| Noise gate threshold | Line 4, `THRESHOLD` | `-40` dB | Signal level below which the gate closes. Raise (e.g., -30) for more aggressive gating. |
| Noise gate level reduction | Line 4, `LEVEL-REDUCTION` | `-24` dB | How much the gated signal is attenuated. Lower (e.g., -40) for stronger silencing. |
| Noise gate attack | Line 4, `ATTACK` | `10` ms | How fast the gate opens when signal exceeds threshold. |
| Noise gate decay | Line 4, `DECAY` | `100` ms | How fast the gate closes after signal drops below threshold. |
| Noise gate hold | Line 4, `HOLD` | `50` ms | Minimum time the gate stays open after opening. |
| Filter curve points | Line 5, `f0`–`f16` / `v0`–`v16` | (see file) | 17-point EQ curve. `f` values are frequencies in Hz, `v` values are gain in dB. |
| Normalization peak level | Line 7, `PeakLevel` | `-1` dB | Target peak amplitude. `-1` leaves 1 dB headroom. |
| Noise reduction sensitivity | Audacity session (not in macro) | Audacity default | Higher values remove more noise but may introduce artefacts. Set once via **Effect > Noise Reduction** before running the pipeline. |
| Noise reduction frequency smoothing | Audacity session (not in macro) | Audacity default | Smooths the frequency profile; higher values reduce musical noise but blur transients. |
| Noise reduction time smoothing | Audacity session (not in macro) | Audacity default | Smooths over time; higher values reduce noise bursts but may smear speech onsets. |

### Changing Output Channels

The export command in `denoisepipe.py` forces mono output:

```python
do_command(f'Export2: Filename="{output_path}" NumChannels=1')
```

Change `NumChannels=1` to `NumChannels=2` for stereo output.

### Adjusting the Sleep Timer

A 0.1 s pause between files lets Audacity settle:

```python
time.sleep(0.1)
```

Increase this if Audacity struggles with rapid successive imports (e.g., large files or slow machines).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `..does not exist. Ensure Audacity is running with mod-script-pipe.` | Start Audacity first and verify mod-script-pipe is enabled in Preferences > Modules |
| Macro not found / no effect applied | Verify `Denoiseok.txt` is in the correct Audacity Macros directory and the filename matches the `Macro_Denoiseok:` call |
| Audacity slows down over many files | The script already disables undo history during processing. If still slow, increase the sleep timer or process in smaller batches. |
| Noise reduction has no effect | Check the log: if every file fell back to the 0.0–0.5 s segment, Respiro-EN may not be detecting any silence. Try lowering `threshold` or `MIN_SILENCE_DURATION`. |
| `ModuleNotFoundError: No module named 'modules'` | `RESPIRO_PATH` in `denoisepipe.py` does not point to the correct Respiro-EN directory. |
| `FiltrePasse-haut` not recognized | This is the French-locale name for the High-Pass Filter. If your Audacity is in English, replace it with `HighPassFilter` in `Denoiseok.txt`. |