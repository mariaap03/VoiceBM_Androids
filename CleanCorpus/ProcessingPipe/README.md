# ProcessingPipe - Audacity Audio Cleaning Pipeline

Batch audio denoising and enhancement pipeline that processes WAV files through Audacity via its scripting interface (`mod-script-pipe`).

## Prerequisites

- **Audacity** with the `mod-script-pipe` module enabled
- **Python 3** (2.7+ supported, 3 strongly recommended)
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

## How It Works

The pipeline communicates with a running Audacity instance through named pipes. For each WAV file in the input directory, it:

1. Imports the audio into Audacity
2. Applies the `Denoiseok` macro (stereo-to-mono, high-pass filter, noise reduction, noise gate, EQ curve, second noise reduction pass, normalization)
3. Exports the processed audio as mono WAV to the output directory
4. Removes the track from Audacity to free memory

## Setup

### 1. Install the Audacity Macro

Copy `AudacityMacros/Denoiseok.txt` into your Audacity macros directory:

| OS | Macro directory |
|----|-----------------|
| Linux | `~/.audacity-data/Macros/` or `~/.config/audacity/Macros/` |
| macOS | `~/Library/Application Support/audacity/Macros/` |
| Windows | `%APPDATA%\audacity\Macros\` |

The file must be named exactly `Denoiseok.txt` to match the macro call in the script. If you rename it, update the corresponding line in `denoisepipe.py` (see below).

### 2. Configure the Script

Open `denoisepipe.py` and update the two directory constants at **lines 77-78**:

```python
# Update these to match your local directories
in_dir = "/path/to/input/audio"
out_dir = "/path/to/output/audio"
```

- `in_dir` -- directory containing the `.wav` files to process
- `out_dir` -- directory where cleaned files will be saved (must already exist)

## Running the Pipeline

1. **Start Audacity** (it must be running before the script)
2. Run the script:

```bash
python denoisepipe.py
```

The script will log each file as it processes. All output files keep their original filenames and are written to `out_dir` as mono WAV.

## Macro Reference

### Denoiseok.txt (Main Denoising Macro)

This macro applies seven sequential processing steps:

| Step | Effect | Key Parameters | Purpose |
|------|--------|---------------|---------|
| 1 | StereoToMono | -- | Convert to single channel |
| 2 | High-Pass Filter | Frequency=90 Hz, Rolloff=12 dB/oct | Remove low-frequency rumble |
| 3 | Noise Reduction (pass 1) | Current Settings | Reduce background noise |
| 4 | Noise Gate | Threshold=-40 dB, Level-Reduction=-24 dB, Attack=10 ms, Decay=100 ms, Hold=50 ms | Gate out low-level noise in silent sections |
| 5 | Filter Curve (EQ) | 17-point B-spline curve, 67 Hz - 20.8 kHz | Shape frequency response for speech clarity |
| 6 | Noise Reduction (pass 2) | Current Settings | Second denoising pass |
| 7 | Normalize | Peak Level=-1 dB, Remove DC Offset=yes | Normalize volume, prevent clipping |

**Note on Noise Reduction:** Audacity's Noise Reduction is a two-step process: first you *capture* a noise profile, then you *apply* it. The macro only performs the apply step (Steps 3 and 6 use `<Current Settings>`). You must capture a noise profile manually **before** running the pipeline:

1. Open a representative audio file in Audacity
2. Select a segment that contains **only background noise** (no speech)
3. Go to **Effect > Noise Reduction > Get Noise Profile**
4. Close the file (do not save)

The captured profile stays in Audacity's memory for the entire session and is reused for every file the pipeline processes. If your recordings have varying noise characteristics, you may need to run the pipeline in separate batches with a different noise profile for each batch.

### Join.txt (Utility Macro)

Aligns multiple tracks end-to-end and mixes them into a single track. Not used by the main pipeline but available for concatenating audio files manually in Audacity.

## Customizing Parameters

### Changing the Macro Name

If you rename `Denoiseok.txt` to something else (e.g., `MyMacro.txt`), update line 98 in `denoisepipe.py`:

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
| Filter curve points | Line 5, `f0`-`f16` / `v0`-`v16` | (see file) | 17-point EQ curve. `f` values are frequencies in Hz, `v` values are gain in dB. |
| Normalization peak level | Line 7, `PeakLevel` | `-1` dB | Target peak amplitude. `-1` leaves 1 dB headroom. |

### Changing Output Channels

The export command in `denoisepipe.py` line 99 forces mono output:

```python
do_command(f'Export2: Filename="{output_path}" NumChannels=1')
```

Change `NumChannels=1` to `NumChannels=2` for stereo output.

### Adjusting the Sleep Timer

Line 107 adds a 0.1s pause between files to let Audacity settle:

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
| Noise reduction has no effect | You need to set a noise profile in Audacity before running the pipeline (Effect > Noise Reduction > Get Noise Profile on a noise-only selection) |
| `FiltrePasse-haut` not recognized | This is the French-locale name for the High-Pass Filter. If your Audacity is in English, replace it with `HighPassFilter` in `Denoiseok.txt`. |