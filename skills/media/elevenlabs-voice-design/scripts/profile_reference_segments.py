"""Per-segment audio profile keyed to a Whisper-style transcript timeline.

Why this exists: signature vocal tonality often lives in the *contrast* between
segments (e.g., reactive bursts intercut with grounded plain lines), not in
constant whole-clip properties. Whole-clip stats can hide the texture entirely.

Use this script when you want to point at the *specific moments* of a reference
clip that carry the texture the user is reaching for, and translate those
moments into prose for the Voice Design prompt.

Usage:
    # First transcribe the reference via Whisper (or similar) to get segments
    # with (start, end, text) tuples, then either edit the SEGMENTS constant
    # below OR pass --segments-json pointing to a JSON file like:
    #   [{"start": 0.0, "end": 20.4, "text": "..."}, ...]

    ~/.venvs/librosa-tools/bin/python profile_reference_segments.py \\
        --audio /tmp/ref.mp3 \\
        --segments-json /tmp/ref_segments.json

Interpretation:
    stdF0 > 80   = highly reactive/animated moment
    stdF0 < 50   = grounded/conversational moment
    RMS < 0.04   = soft/intimate
    RMS > 0.06   = projected/energetic
    centroid > 1800 = brighter (surprise/energy)
    centroid < 1400 = warmer/lower (dry/self-aware)
"""
import argparse
import json
import sys

import librosa
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, help="Path to reference audio")
    ap.add_argument(
        "--segments-json",
        required=True,
        help="JSON file: list of {start, end, text} dicts (from Whisper or similar)",
    )
    args = ap.parse_args()

    segments = json.load(open(args.segments_json))
    y, sr = librosa.load(args.audio, sr=16000, mono=True)

    print(f"{'time':>14}  {'meanF0':>6} {'stdF0':>6} {'lo-hi':>9}  {'RMS':>6}  {'cent':>5}  text")
    print("-" * 100)

    for seg in segments:
        start, end, txt = seg["start"], seg["end"], seg.get("text", "")
        s_idx = int(start * sr)
        e_idx = int(end * sr)
        clip = y[s_idx:e_idx]
        if len(clip) < sr:
            continue
        f0 = librosa.yin(clip, fmin=80, fmax=500, sr=sr, frame_length=2048)
        voiced = f0[(f0 > 80) & (f0 < 500)]
        if len(voiced) < 10:
            continue
        rms = librosa.feature.rms(y=clip)[0]
        cent = librosa.feature.spectral_centroid(y=clip, sr=sr)[0]
        print(
            f"  {start:5.1f}-{end:5.1f}s"
            f"  {voiced.mean():6.0f}"
            f" {voiced.std():6.0f}"
            f"  {voiced.min():3.0f}-{voiced.max():3.0f}"
            f"   {rms.mean():.4f}"
            f"  {cent.mean():4.0f}"
            f"  {txt[:50]}"
        )

    print()
    print("=== INTERPRETATION GUIDE ===")
    print("  stdF0 > 80  = highly reactive/animated moment")
    print("  stdF0 < 50  = grounded/conversational moment")
    print("  RMS < 0.04  = soft/intimate, RMS > 0.06 = projected")
    print("  centroid > 1800 = bright (surprise/energy)")
    print("  centroid < 1400 = warm (dry/self-aware drop)")
    print()
    print("Look for high-contrast adjacent segments — those define signature texture.")


if __name__ == "__main__":
    main()
