#!/usr/bin/env python3
"""判定一个捕获里的"尾段"是否真的可用：源已停、回路还活着、没削顶。

为什么必须逐条判定
------------------
"计划采 1 s 尾段"不等于每个保存下来的片段都在尾段。保护可能早停（实测有 327–961 帧
就中止的例子），保存的帧数也可能覆盖到源播放段。用跨越源段的窗口算衰减率，
得到的是激励包络而不是环路余振。

六项判据（全部通过才算可用）
---------------------------
1. 元数据一致：`frames` 与实际数组长度一致；`completed_frames < frames` 说明早停。
2. 源已停：分析窗口内 reference 的 RMS 比整段 reference 峰值低 **40 dB 以上**。
3. 有过渡隔离：窗口起点在"最后一个有源帧"之后至少 `--guard` 帧（默认 512）。
4. 回路还活着：窗口内 microphone 的 RMS 比整段最低 5 % 分位（近似底噪）高 **10 dB 以上**，
   否则"安静"和"回路断了"无法区分。
5. 未削顶：窗口内 |microphone| 峰值 < 0.99 满量程。
6. 长度够：窗口长度 ≥ `--min-frames`（默认 2048），否则斜率拟合没有意义。

用法
----
    python scripts/check_tail_window.py --npz <文件> [--start 0] [--frames 16384]
    python scripts/check_tail_window.py --dir <目录>          # 批量，自动取每段末尾

输出每个捕获的 PASS/FAIL 与理由；有任一 FAIL 时退出码非 0。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np


def analyse(path, start=None, frames=None, guard=512, min_frames=2048):
    z = np.load(path, allow_pickle=True)
    ref = np.asarray(z["reference"], dtype=float)
    mic = np.asarray(z["microphone"], dtype=float)
    md = json.loads(str(z["metadata_json"])) if "metadata_json" in z else {}
    n = len(mic)
    if frames is None:
        frames = min(16384, n)
    if start is None:
        start = max(0, n - frames)
    stop = min(n, start + frames)
    win_ref = ref[start:stop]
    win_mic = mic[start:stop]

    reasons = []
    # 1 元数据
    declared = md.get("frames")
    done = md.get("completed_frames")
    if declared is not None and int(declared) != n:
        reasons.append("metadata.frames=%s 与数组长度 %d 不一致" % (declared, n))
    early = done is not None and int(done) < n

    # 2 源已停
    ref_peak = float(np.max(np.abs(ref))) if n else 0.0
    win_ref_rms = float(np.sqrt(np.mean(win_ref ** 2))) if len(win_ref) else 0.0
    peak_db = 20 * np.log10(max(ref_peak, 1e-30))
    win_ref_db = 20 * np.log10(max(win_ref_rms, 1e-30))
    src_stopped = win_ref_db <= peak_db - 40.0
    if not src_stopped:
        reasons.append("窗口内仍有源：ref %.1f dBFS vs 整段峰值 %.1f dBFS（差 %.0f dB < 40）"
                       % (win_ref_db, peak_db, peak_db - win_ref_db))

    # 3 过渡隔离：最后一个有源帧
    thr = ref_peak * 10 ** (-40 / 20.0)
    active = np.where(np.abs(ref) > thr)[0]
    last_active = int(active[-1]) if len(active) else -1
    if last_active >= 0 and start - last_active < guard:
        reasons.append("窗口起点 %d 距最后一个有源帧 %d 只有 %d 帧（需 ≥ %d）"
                       % (start, last_active, start - last_active, guard))

    # 4 回路活着
    floor = float(np.percentile(np.abs(mic), 5)) + 1e-30
    win_mic_rms = float(np.sqrt(np.mean(win_mic ** 2))) if len(win_mic) else 0.0
    alive_db = 20 * np.log10(max(win_mic_rms, 1e-30) / floor)
    if alive_db < 10.0:
        reasons.append("窗口内 mic %.1f dBFS 只比底噪高 %.1f dB（需 ≥ 10），"
                       "无法区分稳定与回路断开" % (20 * np.log10(max(win_mic_rms, 1e-30)), alive_db))

    # 5 削顶
    mx = float(np.max(np.abs(win_mic))) if len(win_mic) else 0.0
    if mx >= 0.99:
        reasons.append("窗口内麦克风削顶：峰值 %.3f 满量程" % mx)

    # 6 长度
    if len(win_mic) < min_frames:
        reasons.append("窗口只有 %d 帧（需 ≥ %d）" % (len(win_mic), min_frames))

    return {
        "file": Path(path).name,
        "window": [int(start), int(stop)],
        "frames": n,
        "completed_frames": done,
        "early_stop": bool(early),
        "ref_peak_dbfs": peak_db,
        "window_ref_dbfs": win_ref_db,
        "window_mic_dbfs": 20 * np.log10(max(win_mic_rms, 1e-30)),
        "alive_over_floor_db": alive_db,
        "peak_fullscale": mx,
        "last_active_frame": last_active,
        "usable": not reasons,
        "reasons": reasons,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--npz", default=None)
    parser.add_argument("--dir", default=None)
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--guard", type=int, default=512)
    parser.add_argument("--min-frames", type=int, default=2048)
    args = parser.parse_args(argv)

    if args.npz:
        targets = [args.npz]
    elif args.dir:
        targets = sorted(str(p) for p in Path(args.dir).glob("seg_*.npz"))
        if not targets:
            raise SystemExit("no seg_*.npz under %s" % args.dir)
    else:
        raise SystemExit("给 --npz 或 --dir")

    ok = True
    for t in targets:
        r = analyse(t, args.start, args.frames, args.guard, args.min_frames)
        tag = "PASS" if r["usable"] else "FAIL"
        print("[%s] %-16s 窗口 %d-%d（%d 帧） ref %+.1f dBFS  mic %+.1f dBFS  "
              "比底噪 %+.1f dB%s"
              % (tag, r["file"], r["window"][0], r["window"][1],
                 r["window"][1] - r["window"][0], r["window_ref_dbfs"],
                 r["window_mic_dbfs"], r["alive_over_floor_db"],
                 "  （早停）" if r["early_stop"] else ""))
        for why in r["reasons"]:
            print("       - %s" % why)
        ok = ok and r["usable"]
    print()
    print("结论：%d 个捕获，%s" % (len(targets), "全部可用" if ok else "存在不可用窗口，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
