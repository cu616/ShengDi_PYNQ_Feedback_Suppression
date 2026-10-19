"""Fit and validate two independent synchronized open-loop captures."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from feedback.calibration import load_capture, fit_path, evaluate_path, export_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("training", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--taps", type=int, default=256)
    parser.add_argument("--ridge", type=float, default=1e-6)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; choose a new model filename")
    try:
        train, validation = load_capture(args.training), load_capture(args.validation)
        model = fit_path(train, args.taps, args.ridge)
        metrics = evaluate_path(model, validation, train)
        export_model(args.output, model, metrics)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")
    print("OPEN_LOOP_PREDICTION_REDUCTION_DB", round(metrics["prediction_reduction_db"], 3))
    print("MODEL_SAVED", args.output)
    print("NOT_A_BOARD_AFC_OR_ASG_RESULT")


if __name__ == "__main__":
    main()
