"""消费 C 的测评软件汇总 v3：字段完整性、门禁一致性、模型身份与同增益配对复核。

B 侧只做两件事：确认一份 v3 汇总能不能直接用于"选模型/判效果"，以及模型哈希对不对得上。
不改 C 的判据、不改原始数据。

判据：
  1. schema_version=3、calculation_version=c-measurement-2.1.0。
  2. 每行必备字段存在；无效尾段必须三项全空且 tail_reasons 非空（不能填 0 当通过）。
  3. 模型身份：model_sha256 在本仓 models/manifest.json 内；coefficients_sha256 必须等于
     该模型的 Q20 数组哈希（loaded_taps==logical_taps）或补零到 512 后的数组哈希
     （logical_taps=256、loaded_taps=512）。哈希口径 little-endian int32。
  4. 256 补零不得标成 candidate。
  5. 同增益配对：gain_q12/hp_volume/bit/fixture/采样率/源/scene/session/模式/尾段区间一致，
     模型可以不同；gain 不符必须两行 invalid。
  6. asg_db 只在 evidence_kind=board_recording 且两行 effect_eligible 时才允许非空。

用法：
  python scripts/consume_summary_v3.py --summary <summary.json> [--csv <summary.csv>]
      [--models models] [--out verdict.json] [--require-pairs]
退出码：0 可消费；1 有阻断问题；2 仅实现缺口的告警（--require-pairs 时按 1 处理）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

SCHEMA_VERSION = 3
CALC_VERSION_PREFIX = "c-measurement-"
BANDS = ("300-1000", "1000-3000", "8200-8600")
HASH_LEN = 64

REQUIRED_FIELDS = (
    "capture_id", "gain_q12", "hp_volume", "bit_sha256", "coefficients_sha256",
    "model_sha256", "model_role", "logical_taps", "loaded_taps", "fixture_id",
    "sample_rate_hz", "source_pcm16_sha256", "scene_sha256", "session_id",
    "comparison_id", "repeat_id", "bypass", "tail_valid", "tail_rms_dbfs",
    "tail_slope_db_per_s", "tail_residual_over_mic_db", "tail_reasons",
    "effect_eligible", "evidence_kind", "protection_triggered", "prediction_saturation",
    "residual_saturation", "gain_saturation", "mix_saturation", "microphone_clipping",
    "mute_during_observation",
)
PAIR_IDENTITY = ("gain_q12", "hp_volume", "bit_sha256", "fixture_id", "sample_rate_hz",
                 "source_pcm16_sha256", "scene_sha256", "session_id", "bypass",
                 "tail_first_frame", "tail_end_frame")


def qhash(values) -> str:
    arr = np.asarray([int(v) for v in values], dtype=np.int64)
    return hashlib.sha256(arr.astype("<i4").tobytes()).hexdigest()


def load_registry(models_dir: Path):
    manifest = json.loads((models_dir / "manifest.json").read_text(encoding="utf-8"))
    reg = {}
    for item in manifest["models"]:
        path = (models_dir / item["file"]).resolve()
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw.decode("utf-8"))
        q = data.get("coefficients_q20") or []
        padded = np.pad(np.asarray(q, dtype=np.int64), (0, max(0, 512 - len(q))))
        reg[digest] = {
            "file": item["file"],
            "fixture_id": data.get("fixture_id"),
            "logical_taps": len(q),
            "role": "candidate" if "candidate_" in path.name else "baseline",
            "coefficients_sha256": qhash(q),
            "padded_512_sha256": qhash(padded),
        }
    return reg


def is_hash(v) -> bool:
    return isinstance(v, str) and len(v) == HASH_LEN and all(c in "0123456789abcdef" for c in v)


def check_row(row, reg, issues, gaps, stats):
    idx = row.get("capture_id", row.get("index"))
    for key in REQUIRED_FIELDS:
        if key not in row:
            issues.append("%s: 缺字段 %s" % (idx, key))
        elif row[key] in (None, "") and key in ("comparison_id", "repeat_id"):
            gaps.setdefault("%s 为空，无法参与配对" % key, set()).add(idx)
    for key in ("bit_sha256", "coefficients_sha256"):
        if row.get(key) is not None and not is_hash(row[key]):
            issues.append("%s: %s 不是 64 位小写十六进制" % (idx, key))

    # 尾段与空值的一致性
    tail = row.get("tail_residual_over_mic_db") or {}
    tail_valid = row.get("tail_valid")
    if tail_valid is False:
        bad = [b for b in BANDS if tail.get(b) is not None]
        if bad:
            issues.append("%s: tail_valid=false 但 %s 有数值（不能拿 0 当通过）" % (idx, bad))
        if not row.get("tail_reasons"):
            issues.append("%s: tail_valid=false 却没有 tail_reasons" % idx)
    elif tail_valid is True:
        missing = [b for b in BANDS if tail.get(b) is None]
        if missing:
            issues.append("%s: tail_valid=true 但 %s 为空" % (idx, missing))
        if row.get("tail_rms_dbfs") is None or row.get("tail_slope_db_per_s") is None:
            issues.append("%s: tail_valid=true 但 RMS/斜率缺失" % idx)

    # 模型身份
    model_sha = row.get("model_sha256")
    if model_sha is not None:
        entry = reg.get(model_sha)
        if entry is None:
            issues.append("%s: model_sha256 不在本仓 manifest 内" % idx)
        else:
            stats["registry_hits"] = stats.get("registry_hits", 0) + 1
            logical, loaded = row.get("logical_taps"), row.get("loaded_taps")
            coef_sha = row.get("coefficients_sha256")
            coef_sha0 = row.get("coefficients_sha256")
            if coef_sha0 == entry["coefficients_sha256"]:
                stats["coef_matches_raw"] = stats.get("coef_matches_raw", 0) + 1
            elif coef_sha0 == entry["padded_512_sha256"] and \
                    entry["padded_512_sha256"] != entry["coefficients_sha256"]:
                stats["coef_matches_padded512"] = stats.get("coef_matches_padded512", 0) + 1
            elif coef_sha0 is not None:
                issues.append("%s: coefficients_sha256 既不是原数组也不是补零数组" % idx)
            if type(logical) is not int or type(loaded) is not int:
                gaps.setdefault("logical_taps/loaded_taps 未知", set()).add(idx)
            else:
                expected = (entry["coefficients_sha256"] if loaded == logical
                            else entry["padded_512_sha256"] if (logical == entry["logical_taps"]
                                                                and loaded == 512) else None)
                if expected is None:
                    issues.append("%s: logical=%s/loaded=%s 与模型注册表不符" % (idx, logical, loaded))
                elif coef_sha != expected:
                    issues.append("%s: coefficients_sha256 与模型不符（补零/身份错误）" % idx)
                if logical == 256 and loaded == 512 and row.get("model_role") != "baseline":
                    issues.append("%s: 256 补零被标成 %r，不得冒充 candidate"
                                  % (idx, row.get("model_role")))
                elif row.get("model_role") != entry["role"]:
                    issues.append("%s: model_role=%r 与注册表 %r 不符"
                                  % (idx, row.get("model_role"), entry["role"]))
            if row.get("fixture_id") != entry["fixture_id"]:
                issues.append("%s: fixture_id 与模型不符" % idx)

    # effect_eligible 的自洽性
    if row.get("effect_eligible") is True:
        blockers = []
        if tail_valid is not True:
            blockers.append("tail_invalid")
        if row.get("evidence_kind") != "board_recording":
            blockers.append("evidence_kind=" + str(row.get("evidence_kind")))
        for key in ("protection_triggered", "microphone_clipping", "mute_during_observation"):
            if row.get(key) is not False:
                blockers.append("%s=%r" % (key, row.get(key)))
        for key in ("prediction_saturation", "residual_saturation", "gain_saturation",
                    "mix_saturation"):
            if row.get(key) is not False:
                blockers.append("%s=%r" % (key, row.get(key)))
        if blockers:
            issues.append("%s: effect_eligible=true 但存在阻断项 %s" % (idx, blockers))


def check_pairs(rows, pairs, issues):
    by_id = {r.get("capture_id"): r for r in rows}
    seen = set()
    for pair in pairs:
        cid = pair.get("comparison_id")
        a, b = by_id.get(pair.get("baseline_capture_id")), by_id.get(pair.get("candidate_capture_id"))
        if a is None or b is None:
            issues.append("%s: 配对的 capture_id 不在 trials 内" % cid)
            continue
        seen.add(cid)
        diffs = [k for k in PAIR_IDENTITY if a.get(k) != b.get(k)]
        if diffs:
            issues.append("%s: 配对身份不一致 %s" % (cid, diffs))
        if a.get("model_sha256") == b.get("model_sha256"):
            issues.append("%s: 基线与候选是同一个模型" % cid)
        both = a.get("effect_eligible") is True and b.get("effect_eligible") is True
        if pair.get("effect_eligible") and not both:
            issues.append("%s: 配对 effect_eligible=true 但行尚未达标" % cid)
        if pair.get("asg_db") is not None:
            if not (both and pair.get("evidence_kind") == "board_recording"):
                issues.append("%s: asg_db 非空但证据级别不够" % cid)
        if pair.get("gain_q12") is not None and a.get("gain_q12") != pair.get("gain_q12"):
            issues.append("%s: 配对 gain 与行实际 gain 不符" % cid)
    return seen


def check_csv(path: Path, rows, issues):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        table = list(csv.DictReader(fh))
    if len(table) != len(rows):
        issues.append("CSV 行数 %d 与 JSON trials %d 不一致" % (len(table), len(rows)))
        return
    for jrow, crow in zip(rows, table):
        for key in ("capture_id", "coefficients_sha256", "bit_sha256"):
            if (jrow.get(key) or "") != (crow.get(key) or ""):
                issues.append("CSV/JSON 不一致：%s %s" % (jrow.get("capture_id"), key))
        for band in BANDS:
            col = "tail_residual_over_mic_db_" + band.replace("-", "_")
            jval = (jrow.get("tail_residual_over_mic_db") or {}).get(band)
            cval = crow.get(col)
            if jval is None and cval not in (None, ""):
                issues.append("CSV 有值而 JSON 为空：%s %s" % (jrow.get("capture_id"), col))
            elif jval is not None and cval not in (None, ""):
                if abs(float(cval) - float(jval)) > 1e-9:
                    issues.append("CSV/JSON 数值不一致：%s %s" % (jrow.get("capture_id"), col))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default=None)
    ap.add_argument("--require-pairs", action="store_true",
                    help="没有实测可用配对时按失败处理")
    args = ap.parse_args()

    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    reg = load_registry(Path(args.models))
    issues, gaps, stats = [], {}, {}

    if summary.get("schema_version") != SCHEMA_VERSION:
        issues.append("schema_version=%r，期望 %d" % (summary.get("schema_version"), SCHEMA_VERSION))
    if not str(summary.get("calculation_version", "")).startswith(CALC_VERSION_PREFIX):
        issues.append("calculation_version=%r 不是 %s" % (summary.get("calculation_version"),
                                                          CALC_VERSION_PREFIX + "x"))

    rows = summary.get("trials") or []
    for row in rows:
        check_row(row, reg, issues, gaps, stats)
    pairs = summary.get("model_pairs") or []
    seen = check_pairs(rows, pairs, issues)

    groups = {}
    for row in rows:
        if row.get("model_role") in ("baseline", "candidate"):
            groups.setdefault(row.get("comparison_id"), []).append(row)
    unpaired = [cid for cid in groups if cid not in seen]
    if unpaired:
        gaps.setdefault("有模型行但没有配对", set()).update(unpaired)

    categories, reasons = {}, {}
    for row in rows:
        categories[str(row.get("category"))] = categories.get(str(row.get("category")), 0) + 1
        for reason in row.get("comparison_reasons") or []:
            reasons[str(reason)] = reasons.get(str(reason), 0) + 1

    coverage = {}
    for key in ("gain_q12", "hp_volume", "bit_sha256", "coefficients_sha256", "model_role",
                "logical_taps", "loaded_taps", "tail_valid", "tail_rms_dbfs",
                "tail_slope_db_per_s", "effect_eligible", "protection_triggered"):
        coverage[key] = sum(1 for r in rows if r.get(key) is not None)
    for band in BANDS:
        coverage["band_" + band] = sum(
            1 for r in rows if (r.get("tail_residual_over_mic_db") or {}).get(band) is not None)

    eligible = sum(1 for r in rows if r.get("effect_eligible") is True)
    real_pairs = sum(1 for p in pairs if p.get("effect_eligible") is True
                     and p.get("evidence_kind") == "board_recording")
    if args.csv:
        check_csv(Path(args.csv), rows, issues)

    verdict = {
        "summary": str(args.summary),
        "schema_version": summary.get("schema_version"),
        "calculation_version": summary.get("calculation_version"),
        "evidence_kind": sorted({r.get("evidence_kind") for r in rows if r.get("evidence_kind")}),
        "rows": len(rows),
        "model_pairs": len(pairs),
        "effect_eligible_rows": eligible,
        "effect_eligible_real_pairs": real_pairs,
        "consumable_as_is": not issues,
        "blocking_issues": issues,
        "gaps": {k: {"rows": len(v), "examples": sorted(map(str, v))[:3]}
                 for k, v in sorted(gaps.items())},
        "categories": categories,
        "row_blocking_reasons": reasons,
        "model_registry_hits": stats.get("registry_hits", 0),
        "coef_hash_matches_raw_array": stats.get("coef_matches_raw", 0),
        "coef_hash_matches_padded512": stats.get("coef_matches_padded512", 0),
        "field_coverage": coverage,
        "note": "本脚本只判字段与门禁自洽性，不判抗啸叫性能，也不把软件夹具当实测。",
    }
    text = json.dumps(verdict, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)

    if issues:
        return 1
    if args.require_pairs and real_pairs == 0:
        print("\n没有来自 board_recording 的可用配对，按 --require-pairs 记失败", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
