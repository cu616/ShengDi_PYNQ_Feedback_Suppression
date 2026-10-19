"""Generate independent SYNTHETIC calibration fixtures, never board evidence."""
import argparse
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from feedback.calibration import Capture, save_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    h = np.zeros(256)
    k = np.arange(96)
    h[24:120] = 0.15 * np.exp(-k/18) * np.cos(k*0.4)
    for name, seed in (("training", 471), ("validation", 982)):
        rng = np.random.default_rng(seed)
        u = rng.uniform(-0.08, 0.08, 16384)
        y = np.convolve(u, np.r_[0, h])[:len(u)] + rng.normal(0, 0.0001, len(u)) + 0.003
        c = Capture(u, y, 48828.125,
                    {"schema_version": 1, "capture_id": "synthetic-demo-" + name,
                     "source": "synthetic", "forward_path_open": True,
                     "alignment": "same_i2s_frame", "dropped_frames": 0})
        save_capture(args.directory / (name + ".npz"), c)
    np.save(args.directory / "known_path.npy", h)
    print("SYNTHETIC_ONLY", args.directory)


if __name__ == "__main__":
    main()
