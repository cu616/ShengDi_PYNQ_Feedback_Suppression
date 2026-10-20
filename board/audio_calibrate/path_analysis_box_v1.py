"""板上一次性静默分析：只读标定数据，不加载 overlay、不播放、不采集。

这不是唯一入口。数据在谁手里就在谁那儿跑，等价命令是：
    本地  python scripts/analyze_path.py --data-dir <含三个文件的目录> --output ...
板卡只在"采集"和"实测"时需要；分析只要三个文件。

需要在板卡 base/audio/audio_calibrate 目录下执行：

    %run path_analysis_box_v1.py

需要同目录已有：training_box_v1.npz、validation_box_v1.npz、
candidate_box_v1_256.json，以及从仓库上传的 calibration.py、path_analysis.py。

产出 path_analysis_v1.json（已存在则拒绝覆盖，约 25 KB），内容不含任何原始录音，
可以直接下载发回，用来确定现场该测哪些增益。
耗时：本地同规模数据约 2 秒，板上预计 1-3 分钟（最慢的是 512 抽头拟合）。
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

from calibration import load_capture          # noqa: E402
from path_analysis import analyze_captures, load_model_artifact, report_lines  # noqa: E402

TRAINING = "training_box_v1.npz"
VALIDATION = "validation_box_v1.npz"
MODEL = "candidate_box_v1_256.json"
OUTPUT = "path_analysis_v1.json"


def sha256_file(name):
    digest = hashlib.sha256()
    with open(name, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    for name in (TRAINING, VALIDATION, MODEL):
        if not Path(name).exists():
            raise FileNotFoundError(name + " not found; run this in base/audio/audio_calibrate")
    if Path(OUTPUT).exists():
        raise FileExistsError(OUTPUT + " exists; keep the previous result and rename before rerunning")

    # 先给出身份信息，便于事后确认用的是哪一份数据、哪一个模型。
    print("FILES", json.dumps({name: {"sha256": sha256_file(name),
                                      "bytes": Path(name).stat().st_size}
                               for name in (TRAINING, VALIDATION, MODEL)}), flush=True)

    training = load_capture(TRAINING)
    validation = load_capture(VALIDATION)
    model = load_model_artifact(MODEL)
    print("MODEL taps=%d training=%s mode=%s" % (
        model["taps"], model.get("training_capture_id"), model.get("status", "unknown")),
        flush=True)

    result = analyze_captures(training, validation, model)
    result["provenance"] = {
        "training_sha256": sha256_file(TRAINING),
        "validation_sha256": sha256_file(VALIDATION),
        "model_sha256": sha256_file(MODEL),
        "model_status": model.get("status"),
        "numpy": getattr(__import__("numpy"), "__version__", "unknown"),
    }

    for line in report_lines(result):
        print(line, flush=True)

    with Path(OUTPUT).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("PATH_ANALYSIS_DONE", OUTPUT, "NO_AUDIO_PLAYED_NO_RECORDING_UPLOADED", flush=True)


if __name__ == "__main__":
    main()
