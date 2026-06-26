"""Compare audio profiles: a reference clip vs N candidate variants.

Use after a Voice Design round produces one near-miss and 1-2 misses, to
identify *which acoustic dimensions* the misses drifted on. The diff drives
the next prompt rewrite — see SKILL.md §6a.

Usage:
    ~/.venvs/librosa-tools/bin/python compare_variants_to_ref.py \\
        --ref /tmp/alekirser_sample.mp3 \\
        --variant v6-1:/path/to/v6/variant-1.mp3 \\
        --variant v6-2:/path/to/v6/variant-2.mp3 \\
        --variant v6-3:/path/to/v6/variant-3.mp3

Output: side-by-side table + per-variant diff vs reference. Interpret with
the failure-mode → prompt-directive table in SKILL.md §6a.
"""
import argparse
import sys

import librosa
import numpy as np


def profile(path, label):
    y, sr = librosa.load(path, sr=16000, mono=True)
    dur = len(y) / sr
    f0 = librosa.yin(y, fmin=80, fmax=500, sr=sr, frame_length=2048)
    voiced = f0[(f0 > 80) & (f0 < 500)]
    rms = librosa.feature.rms(y=y)[0]
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)

    # Pitch variability within 2-second windows (intra-phrase liveness)
    win = int(2.0 * sr)
    window_stds = []
    for i in range(0, len(y) - win, win):
        wf0 = librosa.yin(y[i:i + win], fmin=80, fmax=500, sr=sr, frame_length=2048)
        wv = wf0[(wf0 > 80) & (wf0 < 500)]
        if len(wv) > 10:
            window_stds.append(wv.std())
    inter_phrase_std = float(np.mean(window_stds)) if window_stds else 0.0

    return {
        "label": label,
        "dur": dur,
        "f0_mean": float(voiced.mean()) if len(voiced) else 0,
        "f0_median": float(np.median(voiced)) if len(voiced) else 0,
        "f0_std_overall": float(voiced.std()) if len(voiced) else 0,
        "f0_std_intra_phrase": inter_phrase_std,
        "f0_p25": float(np.percentile(voiced, 25)) if len(voiced) else 0,
        "f0_p75": float(np.percentile(voiced, 75)) if len(voiced) else 0,
        "rms_mean": float(rms.mean()),
        "centroid_mean": float(cent.mean()),
        "rolloff_85": float(rolloff.mean()),
        "onsets_per_sec": len(onsets) / dur if dur > 0 else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="Reference audio file")
    ap.add_argument(
        "--variant",
        action="append",
        required=True,
        help="LABEL:PATH for each variant (repeat for multiple)",
    )
    args = ap.parse_args()

    ref = profile(args.ref, "REF")
    variants = []
    for spec in args.variant:
        if ":" not in spec:
            print(f"--variant must be LABEL:PATH, got {spec!r}", file=sys.stderr)
            sys.exit(2)
        label, path = spec.split(":", 1)
        variants.append(profile(path, label))

    all_rows = [ref] + variants
    header = (
        f"{'voice':16} {'dur':>5} {'F0mean':>7} {'F0medi':>7} "
        f"{'F0std':>6} {'F0intra':>7} {'P25/P75':>10} "
        f"{'RMS':>7} {'cent':>5} {'roll':>5} {'on/s':>5}"
    )
    print(header)
    print("-" * len(header))
    for r in all_rows:
        print(
            f"{r['label']:16}"
            f" {r['dur']:5.1f}"
            f" {r['f0_mean']:7.0f}"
            f" {r['f0_median']:7.0f}"
            f" {r['f0_std_overall']:6.0f}"
            f" {r['f0_std_intra_phrase']:7.0f}"
            f"  {r['f0_p25']:3.0f}/{r['f0_p75']:3.0f}"
            f"  {r['rms_mean']:.4f}"
            f" {r['centroid_mean']:5.0f}"
            f" {r['rolloff_85']:5.0f}"
            f" {r['onsets_per_sec']:5.1f}"
        )

    print()
    print("=== DIFF vs reference ===")
    for r in variants:
        print(f"\n{r['label']}:")
        print(f"  F0 mean:        {r['f0_mean']:.0f} Hz  (ref {ref['f0_mean']:.0f}, "
              f"diff {r['f0_mean'] - ref['f0_mean']:+.0f})  ← register/pitch height")
        print(f"  F0 std overall: {r['f0_std_overall']:.0f}    (ref {ref['f0_std_overall']:.0f}, "
              f"diff {r['f0_std_overall'] - ref['f0_std_overall']:+.0f})  ← lilt/variation")
        print(f"  F0 std/phrase:  {r['f0_std_intra_phrase']:.0f}    (ref {ref['f0_std_intra_phrase']:.0f}, "
              f"diff {r['f0_std_intra_phrase'] - ref['f0_std_intra_phrase']:+.0f})  ← within-utterance liveness")
        print(f"  RMS mean:       {r['rms_mean']:.4f} (ref {ref['rms_mean']:.4f}, "
              f"diff {r['rms_mean'] - ref['rms_mean']:+.4f})  ← loudness/projection")
        print(f"  Centroid:       {r['centroid_mean']:.0f} Hz (ref {ref['centroid_mean']:.0f}, "
              f"diff {r['centroid_mean'] - ref['centroid_mean']:+.0f})  ← brightness/warmth")
        print(f"  Onsets/sec:     {r['onsets_per_sec']:.1f}    (ref {ref['onsets_per_sec']:.1f}, "
              f"diff {r['onsets_per_sec'] - ref['onsets_per_sec']:+.1f})  ← cadence")


if __name__ == "__main__":
    main()
