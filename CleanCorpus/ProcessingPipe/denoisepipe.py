#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Audacity batch audio denoising pipeline with automatic noise profile capture.

For each WAV file the pipeline:
  1. Detects breath/silence regions with Respiro-EN (no speech, background noise only).
  2. Selects the longest detected silence in Audacity and captures the noise profile.
  3. Runs the Denoiseok macro (which uses <Current Settings> for Noise Reduction).
  4. Exports the processed file as mono WAV.

Requires Audacity to be running with mod-script-pipe enabled before launching.
"""

import os
import sys
import time
import torch

# ---------------------------------------------------------------------------
# Respiro-EN – automatic silence / breath detection
# ---------------------------------------------------------------------------
RESPIRO_PATH = "/home/mae/Documents/stage_L3_software/respiro_en/Respiro-en"
sys.path.insert(0, RESPIRO_PATH)

from modules import DetectionNet, BreathDetector  # noqa: E402

# Minimum duration (seconds) a detected silence must have to be used as the
# noise-profile source.  Intervals shorter than this are ignored; if none
# qualify the pipeline falls back to the first 0.5 s of the file.
MIN_SILENCE_DURATION = 0.3


def init_breath_detector():
    """Load the Respiro-EN model once for the whole session.

    Returns a ready-to-call BreathDetector instance.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(
        os.path.join(RESPIRO_PATH, "respiro-en.pt"),
        map_location=device,
        weights_only=False,
    )
    model = DetectionNet().to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    print(f"Respiro-EN loaded on {device}.")
    return BreathDetector(model, device=device)


def find_noise_profile_segment(detector, wav_path, min_duration=MIN_SILENCE_DURATION):
    """Return (start, end) in seconds of the best silence for noise profiling.

    Uses Respiro-EN to find breath / pause intervals (non-speech regions that
    carry background noise).  The longest qualifying interval is chosen so that
    Audacity has the most representative noise sample.

    Falls back to the first 0.5 s of the file when:
      - Respiro-EN detects no intervals, or
      - all detected intervals are shorter than *min_duration*, or
      - an error occurs during detection.
    """
    try:
        tree = detector(wav_path, threshold=0.064, min_length=20)
        if tree:
            best = max(sorted(tree), key=lambda iv: iv.end - iv.begin)
            if (best.end - best.begin) >= min_duration:
                return best.begin, best.end
    except Exception as exc:
        print(f"    [Respiro-EN] Detection failed ({exc}); using fallback segment.")

    # Fallback: the very beginning of the file typically contains room tone
    # before the speaker starts talking.
    return 0.0, 0.5


# ---------------------------------------------------------------------------
# Audacity pipe setup
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    TONAME = "\\\\.\\pipe\\ToSrvPipe"
    FROMNAME = "\\\\.\\pipe\\FromSrvPipe"
    EOL = "\r\n\0"
else:
    TONAME = "/tmp/audacity_script_pipe.to." + str(os.getuid())
    FROMNAME = "/tmp/audacity_script_pipe.from." + str(os.getuid())
    EOL = "\n"

if not os.path.exists(TONAME):
    print(f"{TONAME} ..does not exist.  Ensure Audacity is running with mod-script-pipe.")
    sys.exit()
if not os.path.exists(FROMNAME):
    print(f"{FROMNAME} ..does not exist.  Ensure Audacity is running with mod-script-pipe.")
    sys.exit()

TOFILE = open(TONAME, "w")
FROMFILE = open(FROMNAME, "rt")


def send_command(command):
    """Send a single command to Audacity."""
    TOFILE.write(command + EOL)
    TOFILE.flush()


def get_response():
    """Read and return Audacity's response to the last command."""
    result = ""
    line = ""
    while True:
        result += line
        line = FROMFILE.readline()
        if line == "\n" and len(result) > 0:
            break
    return result


def do_command(command):
    """Send one command and return the response."""
    send_command(command)
    response = get_response()
    print(f"[cmd] {command!r}  →  {response.strip()!r}")
    return response


# ---------------------------------------------------------------------------
# Directory configuration – update these to match your local paths
# ---------------------------------------------------------------------------
in_dir = "/home/mae/Documents/idmc/master1/university/s2/supervised_project/corpus/Androids-Corpus/Androids-Corpus/Interview-Task/audio/HC"
out_dir = "/home/mae/Documents/idmc/master1/university/s2/supervised_project/corpus/Androids-Corpus/Androids-Corpus/Interview-Task/audio/HC_cleaned"

filenames = [f for f in os.listdir(in_dir) if f.lower().endswith(".wav")]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def apply_macro(filenames, in_dir, out_dir, detector):
    """Process every WAV file through the Denoiseok macro.

    For each file:
      1. Import into Audacity.
      2. Find the best silence with Respiro-EN.
      3. Select that segment and capture the noise profile (GetNoiseProfile:).
      4. Select all and run the Denoiseok macro (uses <Current Settings>).
      5. Export as mono WAV and remove the track.
    """
    # Disable undo history to prevent Audacity from slowing down across files.
    do_command("SetPreference: Name=GUI/MaxUndoLevels Value=0 Reload=0")

    for f in filenames:
        input_path = os.path.abspath(os.path.join(in_dir, f))
        output_path = os.path.abspath(os.path.join(out_dir, f))

        print(f"\n--- Processing: {f} ---")

        do_command(f'Import2: Filename="{input_path}"')

        # --- automatic noise profile capture ---
        start, end = find_noise_profile_segment(detector, input_path)
        print(f"    Noise profile segment: {start:.3f}s – {end:.3f}s")

        # Select only the silence segment and tell Audacity to learn the
        # noise profile from it.  This replaces the manual
        # "Effect > Noise Reduction > Get Noise Profile" step.
        do_command(f"SelectTime: Start={start:.4f} End={end:.4f}")
        do_command("GetNoiseProfile:")

        # --- apply full denoising macro ---
        # SelectAll restores full-track selection before the macro runs.
        # The macro's NoiseReduction steps use <Current Settings>, which now
        # refers to the profile just captured above.
        do_command("SelectAll:")
        do_command("Macro_Denoiseok:")
        do_command(f'Export2: Filename="{output_path}" NumChannels=1')

        # Remove the track to free memory before the next file.
        do_command("SelectAll:")
        do_command("RemoveTracks:")

        # Small pause so Audacity can settle between files.
        time.sleep(0.1)

    # Restore undo history to its default after the batch.
    do_command("SetPreference: Name=GUI/MaxUndoLevels Value=10 Reload=0")


detector = init_breath_detector()
apply_macro(filenames, in_dir, out_dir, detector)