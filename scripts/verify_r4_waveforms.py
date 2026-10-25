"""独立复核 r4 五个原件的整数算术与两组 FIR 配对（波形侧）。

判据分成四层，任一层不过就整体不过：

  1. **包完整性**：`manifest.json` 里每个文件的 sha256 与字节数，逐条重算。
  2. **整数算术**（4 个 replay 试次 + 1 个 60 s 尾环）：
       played[n]  = reference[n]·2²³            （reference 已核为 k/2²³）
       acc[n]     = Σ_k q[k]·played[n−1−k]      （lag_first=1，从右往左取历史）
       prediction = clip(round_shift(acc, 20), ±2²³)
       residual   = mic                       （bypass 臂：预测不参与）
                    clip(mic − prediction)    （FIR on 臂）
       output[n]  = clip(source[n]·256 + gain_q12(residual[n−2]), ±2²³)
     前 512 帧的 FIR 历史在环外、不可知，一律剔除；output 检查只用**记录的**
     residual，因此与 FIR 无关，是独立的第二把尺。
  3. **受迫响应窗**：begin = max(first+512, 0.2·fs)，stop = min(end, len(source)−0.01·fs)，
     与 C 的 `source_response` 同口径；总电平与三带用 Hann + `2/(N·Σw²)` 功率积分。
  4. **配对**：ON−OFF 的总与三带，按 repeat 分别给，不取平均。

用法：
  python scripts/verify_r4_waveforms.py \
      --pack   D:/Always/QianSai/_inbox/2026-10-25_r4_npz \
      --model  models/room_v1/calibrated_20261024.json \
      --summary-v3 D:/Always/QianSai/_inbox/2026-10-25_r4_to_b/summary-v3.json \
      --out-dir report/verification/rc01-r4-2026-10-25/waveform
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

BANDS = ((300, 1000), (1000, 3000), (8200, 8600))
SCALE = 2 ** 23
# 对照容差：同一口径下本侧与汇总/复核只应有浮点末位差（实测 ≤7.1e−15），
# 1e−3 dB 既容得下末位噪声，也挡得住"改 1 dB"这类伪造。
TOL_DB = 1e-3
# r4 包按角色应恰有的件数：两臂各两次 + 一个 60 s 尾环。
EXPECTED_ROLES = {"fir_off": 2, "fir_on": 2, "continuous": 1}


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rounded_shift(value, bits):
    """整数右移，四舍五入远离零；与 RTL/驱动的实现逐位一致。"""
    value = np.asarray(value, dtype=np.int64)
    magnitude = (np.abs(value) + (1 << (bits - 1))) >> bits
    return np.where(value < 0, -magnitude, magnitude)


def gain_pcm(value, gain_q12):
    return np.clip(rounded_shift(np.asarray(value, dtype=np.int64) * gain_q12, 12),
                   -SCALE, SCALE - 1)


def check_package(pack):
    man_path = Path(pack) / "manifest.json"
    if not man_path.exists():
        return None, [{"file": "manifest.json", "status": "missing"}]
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows, ok = [], True
    for name, rec in man["files"].items():
        p = Path(pack) / name
        if not p.exists():
            rows.append({"file": name, "status": "missing"})
            ok = False
            continue
        raw = p.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        good = (digest == rec.get("sha256")) and (len(raw) == rec.get("bytes"))
        rows.append({"file": name, "bytes": len(raw), "bytes_expected": rec.get("bytes"),
                     "sha256": digest, "sha256_expected": rec.get("sha256"),
                     "status": "ok" if good else "mismatch"})
        ok = ok and good
    return ok, rows


def as_text(value):
    """npz 里 metadata_json 是 0 维字符串数组，直接 dict 传入时是 str；两种都要能吃。"""
    inner = getattr(value, "item", None)
    return str(inner()) if callable(inner) else str(value)


def load_trial(path):
    d = np.load(path)
    return {k: d[k] for k in d.files}


def arithmetic(cap, model_q20=None, with_output=True, bypass=None):
    """逐样本重算 prediction / residual / output，返回失配计数与剔除帧数。

    `bypass` 必须由调用方从 metadata 传入——npz 数组里没有这个字段，
    用 `cap.get("bypass")` 会恒为 None，把 bypass 臂当成 FIR-on 臂算。
    """
    ref = np.asarray(cap["reference"], dtype=np.float64)
    played = np.rint(ref * SCALE).astype(np.int64)
    resid_exact = np.all(np.rint(ref * SCALE) == ref * SCALE)
    mic = np.rint(np.asarray(cap["microphone"], dtype=np.float64) * SCALE).astype(np.int64)
    pred_rec = np.asarray(cap["prediction_pcm"], dtype=np.int64)
    res_rec = np.asarray(cap["residual_pcm"], dtype=np.int64)
    q = np.asarray(model_q20 if model_q20 is not None
                   else cap["coefficients_q20"], dtype=np.int64)
    n = len(played)
    if n <= len(q):
        return {"status": "capture_shorter_than_taps"}

    acc = np.convolve(played, np.r_[np.int64(0), q])[:n]
    pred = np.clip(rounded_shift(acc, 20), -SCALE, SCALE - 1)
    skip = len(q)
    residual = mic if bypass else np.clip(mic - pred, -SCALE, SCALE - 1)

    out = {"taps": int(len(q)), "frames": int(n), "history_excluded_frames": int(skip),
           "reference_is_exact_pcm": bool(resid_exact),
           "prediction_mismatches": int(np.count_nonzero(pred[skip:] != pred_rec[skip:])),
           "prediction_evaluated_frames": int(n - skip),
           "residual_mismatches": int(np.count_nonzero(residual[skip:] != res_rec[skip:])),
           "residual_evaluated_frames": int(n - skip),
           "mic_full_scale_samples": int(np.count_nonzero((mic <= -SCALE) | (mic >= SCALE - 1)))}

    if with_output and "source_pcm16" in cap:
        meta = json.loads(as_text(cap["metadata_json"]))
        first = int(meta["first_frame"])
        gain_q12 = int(meta["gain_q12"])
        source = np.asarray(cap["source_pcm16"], dtype=np.int64)
        idx = np.arange(first, first + n)
        injected = np.zeros(n, dtype=np.int64)
        valid = idx < len(source)
        injected[valid] = source[idx[valid]] * 256
        # 只用**记录的** residual，因此这一步与 FIR 无关。
        expected = np.clip(injected[2:] + gain_pcm(res_rec[:-2], gain_q12), -SCALE, SCALE - 1)
        out["output_mismatches"] = int(np.count_nonzero(played[2:] != expected))
        out["output_evaluated_frames"] = int(n - 2)
        out["gain_q12"] = gain_q12
    else:
        out["output_mismatches"] = None
        out["output_evaluated_frames"] = 0
    out["bit_exact"] = (out["prediction_mismatches"] == 0 and out["residual_mismatches"] == 0
                        and (out["output_mismatches"] in (0, None)))
    return out


def response_window(meta, n_source, rate):
    """C 的 source_response 同口径：剔掉未知 FIR 历史与固定 fade。"""
    first, end = int(meta["first_frame"]), int(meta["completed_frames"])
    begin = max(first + 512, int(0.2 * rate))
    stop = min(end, n_source - int(0.01 * rate))
    return begin, stop, max(0, stop - begin)


def response_metrics(cap, meta):
    """总电平与三带功率，窗与门限都与 C 的 source_response 一致。"""
    rate = float(np.asarray(cap["sample_rate_hz"]).item())
    mic = np.asarray(cap["microphone"], dtype=np.float64)
    first = int(meta["first_frame"])
    begin, stop, frames = response_window(meta, int(meta["source_frames"]), rate)
    x = mic[begin - first:stop - first].copy()
    x -= x.mean()
    level = float(20 * np.log10(max(float(np.std(x)), 1e-12)))
    window = np.hanning(len(x))
    power = np.abs(np.fft.rfft(x * window)) ** 2
    freq = np.fft.rfftfreq(len(x), 1 / rate)
    scale = 2 / (len(x) * np.sum(window ** 2))
    bands = {}
    for low, high in BANDS:
        mask = (freq >= low) & (freq < high)
        bands["%d-%d" % (low, high)] = float(10 * np.log10(float(power[mask].sum() * scale)))
    return {"first_frame": begin, "end_frame": stop, "frames": frames,
            "rms_dbfs": level, "bands_dbfs": bands}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True, help="解包后的 r4-review-return 目录")
    ap.add_argument("--model", default="models/room_v1/calibrated_20261024.json")
    ap.add_argument("--summary-v3", default=None, help="C 的 summary-v3.json（取 fir_switch_pairs）")
    ap.add_argument("--c-review", default=None,
                    help="C 的 a-63f6a69-waveform-review.json；给了就逐文件对一次电平与失配计数")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    pack = Path(args.pack)
    out = Path(args.out_dir) if args.out_dir else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    lines = []

    def say(text=""):
        print(text)
        lines.append(text)

    failures = []          # [(代码, 说明)]：空才允许返回 0

    def fail(code, detail):
        failures.append({"code": code, "detail": detail})
        say("  [不合格] %s：%s" % (code, detail))

    say("=" * 78)
    say("[1] 包完整性（%s）" % pack)
    pkg_ok, pkg_rows = check_package(pack)
    if pkg_ok is None:
        say("  manifest.json 缺失，无法核对")
        fail("manifest_missing", "manifest.json 不存在，无法核对任何哈希")
        say("\n判定：**不合格**（1 项）— 不产出合格测量结果")
        if out:
            (out / "waveform.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            (out / "waveform.json").write_text(
                json.dumps({"ok": False, "failures": failures}, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8")
        return 2
    for r in pkg_rows:
        if r["status"] == "missing":
            say("  %-24s 缺文件" % r["file"])
        else:
            say("  %-24s %8d B  sha %s  %s"
                % (r["file"], r["bytes"], r["sha256"][:16],
                   "一致" if r["status"] == "ok" else "**不符**"))
    say("  结论：%s" % ("%d/%d 一致" % (sum(1 for r in pkg_rows if r["status"] == "ok"),
                                          len(pkg_rows)) if pkg_ok
                        else "**有文件不符或缺失**"))
    if not pkg_ok:
        bad = [r["file"] for r in pkg_rows if r["status"] != "ok"]
        fail("package_integrity", "文件哈希/字节数不符或缺失：%s" % bad)

    model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    q20 = np.asarray(model["coefficients_q20"], dtype=np.int64)
    q_sha = hashlib.sha256(q20.astype("<i4").tobytes()).hexdigest()

    trials = ["07-fir-off.npz", "09-fir-on.npz", "11-fir-on.npz", "13-fir-off.npz"]
    say("\n[2] 整数算术（4 个 replay 试次）")
    say("  模型 %s  q20=%s  taps=%d  lag_first=%d"
        % (Path(args.model).name, q_sha[:16], len(q20), model["lag_first"]))
    results = {}
    for name in trials:
        p = pack / name
        if not p.exists():
            say("  %-18s 缺文件" % name)
            continue
        try:
            cap = load_trial(p)
            meta = json.loads(as_text(cap["metadata_json"]))
            r = arithmetic(cap, bypass=bool(meta["bypass"]))
        except Exception as exc:                      # 结构损坏也要是"不合格"，不是崩溃
            fail("trial_unreadable", "%s：%s" % (name, exc))
            continue
        r.update(file=name, capture_id=meta["capture_id"], bypass=bool(meta["bypass"]),
                 gain_q12=int(meta["gain_q12"]), hp_volume=int(meta["hp_volume"]),
                 coefficients_sha256=meta.get("coefficients_sha256"))
        r["response"] = response_metrics(cap, meta)
        results[name] = r
        say("  %-18s bypass=%-5s pred 不符 %d/%d｜residual 不符 %d/%d｜output 不符 %d/%d｜满幅 %d"
            % (name, r["bypass"], r["prediction_mismatches"], r["prediction_evaluated_frames"],
               r["residual_mismatches"], r["residual_evaluated_frames"],
               r["output_mismatches"], r["output_evaluated_frames"], r["mic_full_scale_samples"]))
        bound = r["coefficients_sha256"] == q_sha
        say("  %-18s 模型绑定 %s；响应窗 %d–%d（%d 帧），总 %.3f dBFS"
            % ("", "一致" if bound else "**不一致**",
               r["response"]["first_frame"], r["response"]["end_frame"],
               r["response"]["frames"], r["response"]["rms_dbfs"]))
        r["model_bound"] = bool(bound)
        if not bound:
            fail("model_binding", "%s 记录的 coefficients_sha256 与给定模型不符" % name)
        if not r["bit_exact"]:
            fail("arithmetic", "%s：prediction %d / residual %d / output %s 帧失配"
                 % (name, r["prediction_mismatches"], r["residual_mismatches"],
                    r["output_mismatches"]))

    tail_name = "15-continuous-60s.npz"
    say("\n[3] 60 s 尾环（%s）" % tail_name)
    tail_path = pack / tail_name
    if tail_path.exists():
        cap = load_trial(tail_path)
        meta = json.loads(as_text(cap["metadata_json"]))
        r = arithmetic(cap, model_q20=q20, with_output=False,
                       bypass=bool(meta["bypass"]))
        r.update(file=tail_name, capture_id=meta.get("label"), bypass=bool(meta["bypass"]),
                 coefficients_sha256=meta.get("coefficients_sha256"))
        tail = r
        say("  pred 不符 %d/%d｜residual 不符 %d/%d｜满幅 %d"
            % (r["prediction_mismatches"], r["prediction_evaluated_frames"],
               r["residual_mismatches"], r["residual_evaluated_frames"],
               r["mic_full_scale_samples"]))
        say("  output 检查：包里没有 source_pcm16，本轮**无法重算**（记为未测，不当作通过）")
        tl = meta.get("timeline") or []
        first = int(meta.get("first_frame", 0))
        total = int(meta.get("frames_requested", 0))
        say("  timeline 点 %d，环覆盖帧 %d–%d（%d 帧），占整次 %d 帧的 %.3f%%"
            % (len(tl), first, first + r["frames"] - 1, r["frames"], total,
               100.0 * r["frames"] / max(total, 1)))
        bound = r["coefficients_sha256"] == q_sha
        r["model_bound"] = bool(bound)
        if not bound:
            fail("model_binding", "%s 记录的 coefficients_sha256 与给定模型不符" % tail_name)
        if r["prediction_mismatches"] or r["residual_mismatches"]:
            fail("arithmetic", "%s：prediction %d / residual %d 帧失配"
                 % (tail_name, r["prediction_mismatches"], r["residual_mismatches"]))
    else:
        tail = None
        say("  缺文件")
        fail("missing_file", "%s 不存在" % tail_name)

    roles = {"fir_off": 0, "fir_on": 0, "continuous": 1 if tail is not None else 0}
    for r in results.values():
        roles["fir_off" if r["bypass"] else "fir_on"] += 1
    say("\n[3b] 角色齐备性：期望 %s，实际 %s"
        % (EXPECTED_ROLES, roles))
    if roles != EXPECTED_ROLES:
        fail("package_incomplete",
             "角色件数不符（期望 %s，实际 %s）——少件或多了同一臂的重复件"
             % (EXPECTED_ROLES, roles))

    say("\n[4] 受迫响应窗与三带（Hann，2/(N·Σw²) 功率积分）")
    say("  %-18s %10s %10s %10s %10s" % ("试次", "总", "300-1000", "1000-3000", "8200-8600"))
    for name in trials:
        if name in results:
            b = results[name]["response"]["bands_dbfs"]
            say("  %-18s %+10.3f %+10.3f %+10.3f %+10.3f"
                % (name, results[name]["response"]["rms_dbfs"],
                   b["300-1000"], b["1000-3000"], b["8200-8600"]))

    say("\n[5] 配对 ON−OFF（逐 repeat，不取平均）")
    pairs = [(1, "07-fir-off.npz", "09-fir-on.npz"), (2, "13-fir-off.npz", "11-fir-on.npz")]
    computed = []
    for repeat, off_name, on_name in pairs:
        if off_name not in results or on_name not in results:
            say("  repeat %d 缺文件" % repeat)
            continue
        off, on = results[off_name]["response"], results[on_name]["response"]
        row = {"repeat": repeat, "off_file": off_name, "on_file": on_name,
               "total_db": on["rms_dbfs"] - off["rms_dbfs"], "bands_db": {}}
        for key in off["bands_dbfs"]:
            row["bands_db"][key] = on["bands_dbfs"][key] - off["bands_dbfs"][key]
        computed.append(row)
        say("  repeat %d 总 %+0.4f dB｜300-1000 %+0.4f｜1000-3000 %+0.4f｜8200-8600 %+0.4f"
            % (repeat, row["total_db"], row["bands_db"]["300-1000"],
               row["bands_db"]["1000-3000"], row["bands_db"]["8200-8600"]))

    reference = None
    if args.summary_v3:
        sp = Path(args.summary_v3)
        if not sp.exists():
            say("\n[6] summary-v3 不存在：%s" % sp)
            fail("summary_missing", "显式指定了 --summary-v3，但文件不存在：%s" % sp)
        else:
            try:
                summary = json.loads(sp.read_text(encoding="utf-8"))
                reference = summary.get("fir_switch_pairs") or []
            except Exception as exc:
                reference = None
                say("\n[6] summary-v3 解析失败：%s" % exc)
                fail("summary_unreadable", "--summary-v3 无法解析：%s" % exc)
        if reference is not None:
            say("\n[6] 与 C 的 summary-v3 对照")
            if not reference:
                fail("summary_empty", "--summary-v3 里没有 fir_switch_pairs")
            if len(computed) != len(reference):
                fail("pair_count", "配对组数不一致：本侧 %d、汇总 %d"
                     % (len(computed), len(reference)))
            worst = 0.0
            for got, want in zip(computed, reference):
                d_total = abs(got["total_db"] - want["on_minus_off_response_rms_db"])
                say("  repeat %d 总：本侧 %+0.6f / 汇总 %+0.6f（差 %.2e）"
                    % (got["repeat"], got["total_db"], want["on_minus_off_response_rms_db"], d_total))
                worst = max(worst, d_total)
                say("           配对身份：off %s / on %s，%s"
                    % (str(want.get("off_capture_id"))[:8], str(want.get("on_capture_id"))[:8],
                       "逐帧区间一致" if want.get("window_comparison_valid") else "**区间不一致**"))
                for key, value in (want.get("on_minus_off_band_response_db") or {}).items():
                    d = abs(got["bands_db"][key] - value)
                    worst = max(worst, d)
                    say("           %-10s 本侧 %+0.6f / 汇总 %+0.6f（差 %.2e）"
                        % (key, got["bands_db"][key], value, d))
            say("  最大差 %.3e dB（容差 %.0e；超了就是两套数字对不上）" % (worst, TOL_DB))
            if worst > TOL_DB:
                fail("summary_mismatch", "与 summary-v3 的配对差 %.3e dB 超过容差 %.0e"
                     % (worst, TOL_DB))
            for got, want in zip(computed, reference):
                if not (want.get("window_comparison_valid") is True
                        and want.get("configuration_matches") is True):
                    fail("pair_not_valid",
                         "repeat %s 的配对在汇总里未被判定有效（window/config）" % got["repeat"])

    if args.c_review and not Path(args.c_review).exists():
        say("\n[7] 复核 JSON 不存在：%s" % args.c_review)
        fail("c_review_missing", "显式指定了 --c-review，但文件不存在：%s" % args.c_review)
    elif args.c_review:
        try:
            review = json.loads(Path(args.c_review).read_text(encoding="utf-8"))
        except Exception as exc:
            review = None
            say("\n[7] 复核 JSON 解析失败：%s" % exc)
            fail("c_review_unreadable", "--c-review 无法解析：%s" % exc)
      # 解析成功才进对照
        if review is None:
            review = {}
        say("\n[7] 与 C 的独立波形复核对照（%s）" % Path(args.c_review).name)
        by_file = {r["file"]: r for r in review.get("files", [])}
        worst = 0.0
        for name in trials + [tail_name]:
            mine, theirs = results.get(name) or (tail if name == tail_name else None), by_file.get(name)
            if mine is None or theirs is None:
                say("  %-22s 一侧缺记录" % name)
                fail("c_review_incomplete", "%s 在复核 JSON 里没有对应记录，无法对照" % name)
                continue
            d = abs(mine["response"]["rms_dbfs"] - theirs["response_rms_dbfs"]) \
                if "response" in mine else 0.0
            worst = max(worst, d)
            mine_out = ("未测" if mine["output_mismatches"] is None
                        else str(mine["output_mismatches"]))
            say("  %-22s 算术失配 本侧 %s/%s/%s｜C %s/%s/%s；总电平差 %.2e dB"
                % (name, mine["prediction_mismatches"], mine["residual_mismatches"], mine_out,
                   theirs["independent_arithmetic_mismatches"]["prediction"],
                   theirs["independent_arithmetic_mismatches"]["residual"],
                   theirs["independent_arithmetic_mismatches"]["output"], d))
            for key, value in (theirs.get("response_bands_dbfs") or {}).items():
                if "response" in mine and key in mine["response"]["bands_dbfs"]:
                    worst = max(worst, abs(mine["response"]["bands_dbfs"][key] - value))
            theirs_m = theirs["independent_arithmetic_mismatches"]
            if any(int(theirs_m.get(k) or 0) for k in ("prediction", "residual", "output")):
                fail("c_review_disagrees", "%s：复核侧记录到非零失配 %s" % (name, theirs_m))
        say("  最大差 %.3e（容差 %.0e）；失配计数两侧都为 0 才算对上" % (worst, TOL_DB))
        if worst > TOL_DB:
            fail("c_review_mismatch", "与复核 JSON 的电平/分带差 %.3e 超过容差 %.0e"
                 % (worst, TOL_DB))
    else:
        say("\n[7] 未给 C 的复核 JSON：跳过逐文件对照")

    payload = {"pack": str(pack), "package_ok": bool(pkg_ok), "package_rows": pkg_rows,
               "model": {"file": args.model, "q20_sha256": q_sha, "taps": int(len(q20)),
                         "lag_first": int(model["lag_first"])},
               "trials": results, "tail_60s": tail,
               "pairs_computed": computed,
               "pairs_reference": reference,
               "c_review_compared": bool(args.c_review and Path(args.c_review).exists()),
               "method": ("played=reference·2^23；prediction=clip(round_shift(Σq[k]·played[n−1−k],20))；"
                          "residual=mic（bypass）或 clip(mic−prediction)；"
                          "output=clip(source·256+gain_q12(residual[n−2])) 只用记录 residual"),
               "ok": not failures, "failures": failures,
               "tolerance_db": TOL_DB, "expected_roles": EXPECTED_ROLES,
               "scope": ("整数算术与 14408 帧受迫响应窗；不含全程声学、ASG、听感；"
                         "60 s 文件的 output 因缺 source 未复核")}
    verdict = [""]
    if failures:
        verdict.append("判定：**不合格**（%d 项）— 以下任一项存在时，本次数字只能当诊断，"
                       "不能当合格测量结果：" % len(failures))
        for item in failures:
            verdict.append("  - %s：%s" % (item["code"], item["detail"]))
    else:
        verdict.append("判定：**合格** — 文件齐全（角色件数一致）、模型绑定一致、4 试次算术 0 失配、"
                       "60 s 尾环 prediction/residual 0 失配%s"
                       % ("、与 summary-v3 及复核 JSON 在容差 %.0e 内一致" % TOL_DB
                          if (args.summary_v3 or args.c_review) else "（未显式请求外部对照）"))
    lines.extend(verdict)
    payload["verdict"] = verdict[-1]

    if out:
        (out / "waveform.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
        (out / "waveform.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in verdict:
        print(line)
    if out:
        print("\n输出：%s" % out)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
