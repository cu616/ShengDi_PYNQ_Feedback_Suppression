"""Package the successfully routed replay design; never access the board."""
import hashlib
import json
import re
import shutil
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "board/audio_replay"
WORK = ROOT / "build/work/audio_replay"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    timing = (WORK / "timing.txt").read_text(encoding="utf-8")
    match = re.search(r"^\s*WNS\(ns\)[^\n]*\n[^\n]*\n([^\n]+)", timing, re.MULTILINE)
    values = match[1].split() if match else []
    if (len(values) != 12 or any(float(values[i]) < 0 for i in (0, 4, 8))
            or any(int(values[i]) != 0 for i in (2, 6, 10))):
        raise RuntimeError("refusing to package: setup/hold timing did not pass")
    bit = WORK / "audio_replay.runs/impl_1/system_wrapper.bit"
    rtl = ROOT / "src/rtl/audio_pl_replay.v"
    prior_path = DEST / "manifest.json"
    prior = json.loads(prior_path.read_text(encoding="utf8")) if prior_path.exists() else {}
    unchanged_build = (digest(bit) == prior.get("hashes", {}).get("audio_replay.bit") and
                       all(digest(ROOT / p) == h for p, h in prior.get("build_sources", {}).items()) and
                       bool(prior.get("build_sources")))
    if not unchanged_build and bit.stat().st_mtime < rtl.stat().st_mtime:
        raise RuntimeError("bitstream is older than replay RTL")
    shutil.copyfile(bit, DEST / "audio_replay.bit")
    shutil.copyfile(WORK / "audio_replay.srcs/sources_1/bd/system/hw_handoff/system.hwh",
                    DEST / "audio_replay.hwh")

    def md(text):
        return dict(cell_type="markdown", metadata={}, source=text.splitlines(keepends=True))
    def code(text):
        return dict(cell_type="code", execution_count=None, metadata={}, outputs=[],
                    source=text.splitlines(keepends=True))
    cells = [
        md("# 逐档增益旁路/抵消\n\n先静默选档，再录音，最后一批完成。只开这一本音频Notebook。"
           "箱盖、麦克风、两只音响及Codec音量保持原标定条件。手机只在录音时外放。"
           "最多8档，直放1项加每档2项；录2秒时最多发声40.8秒，整轮预留10–15分钟（分析时间依板卡而定）。"
           "持续尖叫立即断音响电源；输入框不是实时急停。\n\n"
           "## 第1格：静默选档\n音响保持断电，运行下面一格一次。列出可测档位且提示选档完成才继续。"
           "不需填写参数，不需启动手机。失败则返回打印的summary.json，不进入第2格。"),
        code("from pathlib import Path\n"
             "import sys, os, importlib\n"
             "BOARD = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_replay')\n"
             "os.chdir(str(BOARD))\n"
             "if str(BOARD) not in sys.path: sys.path.insert(0, str(BOARD))\n"
             "import replay_tools, replay_session, sweep_plan, sweep_session\n"
             "for module in (replay_tools, replay_session, sweep_plan, sweep_session): importlib.reload(module)\n"
             "if 'replay_trial' in sys.modules: importlib.reload(sys.modules['replay_trial'])\n"
             "plan_path = sweep_session.prepare_sweep()"),
        md("## 第2格：录音2秒\n确认第1格成功；音响断电。运行本格后，等RECORD提示出现，"
           "手机在原位置播放语音，输入RECORD回车立即录2秒。录完停止手机外放。已有source.wav自动复用。"),
        code("assert plan_path is not None, '选档失败，停止并返回第1格摘要'\n"
             "source_path = replay_session.record_source()"),
        md("## 第3格：逐档听音\n停止手机外放，恢复音响供电。执行本格后，现场就绪输入READY。"
           "每项配置完成才提示START；输入后立即播放并采样，约2.4秒后静音。"
           "先直放，再每档抵消→旁路，全部档位事先列出。\n\n"
           "每项结束输入：0无声、1清楚语音且结束安静、2杂音失真、3啸叫增长、4结束仍响。"
           "仅1继续；其他输入或数字异常停止整批，保留已完成配对，不再升档。"
           "若旁路出现啸叫，此档抵消项已先完成。\n\n"
           "结束只下载最后打印路径的summary.json，WAV/NPZ留板。不要Run All。"),
        code("result = sweep_session.run_sweep(plan_path)"),
    ]
    nb = dict(cells=cells, metadata=dict(kernelspec=dict(display_name="Python 3",
                  language="python", name="python3"), language_info=dict(name="python")),
              nbformat=4, nbformat_minor=5)
    (DEST / "replay_trial.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1),
                                            encoding="utf-8", newline="\n")
    names = ["audio_replay.bit", "audio_replay.hwh", "replay_trial.py", "replay_tools.py",
             "replay_session.py", "sweep_plan.py", "sweep_session.py", "replay_calibration.py", "closed_tools.py", "residual_tools.py", "replay_trial.ipynb", "README.md"]
    manifest = dict(schema_version=1, overlay="audio_replay", hardware_executed=False,
                    sample_rate_hz=48828.125, source_frames_max=131072,
                    source_format="signed16 -> signed24 << 8",
                    hashes={n: digest(DEST / n) for n in names if n not in ('replay_trial.ipynb', 'README.md')},
                    notebook_code_sha256=hashlib.sha256(json.dumps(
                        [''.join(c['source']) for c in cells if c['cell_type']=='code'],
                        ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest(),
                    build_sources={p: digest(ROOT / p) for p in (
                        "src/rtl/audio_pl_replay.v", "src/rtl/feedback_fir.v",
                        "src/vendor/pynq_v2_4/iis_ser.vhd", "src/vendor/pynq_v2_4/iis_deser.vhd",
                        "build/scripts/create_audio_replay.tcl", "build/scripts/audio_bringup.xdc")},
                    wns_ns=float(values[0]), whs_ns=float(values[4]),
                    limits="External I/O delay constraints incomplete; not board-validated.")
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = ROOT / "report/verification/audio-replay"
    report.mkdir(parents=True, exist_ok=True)
    for name in ("timing.txt", "utilization.txt", "drc.txt"):
        shutil.copyfile(WORK / name, report / name)
    shutil.copyfile(ROOT / "build/work/audio_replay_test/audio_replay_test.sim/sim_1/behav/xsim/simulate.log",
                    report / "rtl-simulation.txt")
    out = ROOT / "build/packages/audio-replay.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names + ["manifest.json"]:
            z.write(DEST / name, "audio_replay/" + name)
    print("PACKAGE", out, "SHA256", digest(out))
    print("TIMING", manifest["wns_ns"], manifest["whs_ns"])


if __name__ == "__main__":
    main()
