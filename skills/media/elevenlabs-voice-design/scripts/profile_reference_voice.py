#!/usr/bin/env python3
"""Objectively profile a reference voice clip for ElevenLabs Voice Design prompt drafting.

Usage:
    ~/.venvs/librosa-tools/bin/python profile_reference_voice.py /path/to/clip.mp3

Outputs F0 stats, RMS dynamics, spectral centroid, onset rate, with interpretive thresholds
that map to ElevenLabs voice description phrases (see SKILL.md §Reference Profiling).

Setup (one-time):
    uv venv ~/.venvs/librosa-tools --python 3.12
    uv pip install --python ~/.venvs/librosa-tools/bin/python librosa soundfile
"""
import sys
from pathlib import Path


def profile(path: str) -> None:
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=16000, mono=True)
    dur = len(y) / sr
    print(f"file: {path}")
    print(f"duration: {dur:.1f}s")
    print()

    # F0 via YIN — voiced frames only
    f0 = librosa.yin(y, fmin=80, fmax=500, sr=sr, frame_length=2048)
    voiced = f0[(f0 > 80) & (f0 < 500)]
    if len(voiced) == 0:
        print("WARN: no voiced frames detected — wrong file or silence?")
        return

    print("=== PITCH (F0) ===")
    mean_f0 = float(voiced.mean())
    std_f0 = float(voiced.std())
    print(f"  mean:    {mean_f0:.0f} Hz  ({librosa.hz_to_note(mean_f0)})")
    print(f"  median:  {np.median(voiced):.0f} Hz")
    print(f"  range:   {voiced.min():.0f}-{voiced.max():.0f} Hz")
    print(f"  std:     {std_f0:.0f} Hz")
    print(f"  P25/P75: {np.percentile(voiced,25):.0f}/{np.percentile(voiced,75):.0f} Hz")
    # Register interpretation
    if mean_f0 < 180:
        reg = "low feminine OR upper masculine"
    elif mean_f0 < 230:
        reg = "mid feminine"
    elif mean_f0 < 280:
        reg = "higher feminine (still natural, not chirpy)"
    else:
        reg = "very high — chirpy/childlike territory"
    print(f"  → register: {reg}")
    # Expressiveness interpretation
    if std_f0 < 30:
        expr = "even / measured / flat"
    elif std_f0 < 70:
        expr = "natural conversational expressiveness"
    else:
        expr = "REACTIVE expressiveness — pitch jumps with feeling"
    print(f"  → expressiveness: {expr}")
    print()

    # Dynamics
    rms = librosa.feature.rms(y=y)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max)
    rms_mean = float(rms.mean())
    print("=== DYNAMICS ===")
    print(f"  rms mean: {rms_mean:.4f}")
    print(f"  rms range (dB): {rms_db.min():.1f} to {rms_db.max():.1f}")
    if rms_mean < 0.03:
        dyn = "soft / close-mic intimate"
    elif rms_mean < 0.10:
        dyn = "performed-conversational volume"
    else:
        dyn = "loud / projected"
    print(f"  → dynamic: {dyn}")
    print()

    # Timbre
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
    cent_mean = float(cent.mean())
    print("=== TIMBRE ===")
    print(f"  centroid: {cent_mean:.0f} Hz")
    print(f"  rolloff 85%: {rolloff.mean():.0f} Hz")
    if cent_mean < 2000:
        tim = "warm / dark"
    elif cent_mean < 3500:
        tim = "balanced"
    else:
        tim = "bright / airy"
    print(f"  → timbre: {tim}")
    print()

    # Cadence (proxy via onset rate)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    rate = len(onsets) / dur
    print("=== CADENCE ===")
    print(f"  onsets/s: {rate:.1f}")
    if rate < 3.5:
        cad = "slow / unhurried / intimate"
    elif rate < 5:
        cad = "natural conversational pace"
    else:
        cad = "fast / energetic"
    print(f"  → cadence: {cad}")
    print()

    print("=== PROMPT DRAFT HINTS ===")
    print(f"  Use phrases like: '{reg} voice with {expr}, {tim} timbre, {cad} delivery'")
    print("  Then add: distinctive textures from listening, hard exclusions, register-availability flags.")
    print("  Always SEND THE CLIP to the user first to confirm reference before drafting.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: profile_reference_voice.py <audio_file>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    if not Path(path).exists():
        print(f"file not found: {path}", file=sys.stderr)
        sys.exit(1)
    profile(path)
