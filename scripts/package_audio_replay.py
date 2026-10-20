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
    if bit.stat().st_mtime < rtl.stat().st_mtime:
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
        md("# 预录语音 → 音响；麦克风同时闭环采样\n\n"
           "只开这一本音频Notebook。录音2秒；随后直放/旁路/抵消各约2.4秒，"
           "总发声最多7.2秒，含上传配置整轮约5–10分钟。箱盖、接线和两只音响位置不变。"
           "录音时音响断电；播放测试时手机停止外放。持续尖叫立即切断音响电源。\n\n"
           "## 第1格：核验文件（不发声）\n"
           "点击下面代码格，Shift+Enter一次；看到 REPLAY_PACKAGE_OK 才继续。"),
        code("from pathlib import Path\n"
             "import sys, os, importlib\n"
             "BOARD = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_replay')\n"
             "if not BOARD.is_dir():\n"
             "    raise FileNotFoundError('请先把完整程序包上传到 ' + str(BOARD))\n"
             "os.chdir(str(BOARD))\n"
             "if str(BOARD) not in sys.path: sys.path.insert(0, str(BOARD))\n"
             "import replay_tools, replay_session\n"
             "importlib.reload(replay_tools)\n"
             "importlib.reload(replay_session)\n"
             "if 'replay_trial' in sys.modules: importlib.reload(sys.modules['replay_trial'])\n"
             "replay_session.check_package()\n"
             "replay_session.load_scene(BOARD.parent / 'audio_closed/field_setup.json')\n"
             "print('SCENE_FILE_OK; NO_AUDIO_STARTED')"),
        md("## 第2格：录一次语音（音响断电）\n"
           "先运行本格。等 RECORD 提示出现后，让手机在原位置播放语音，输入 RECORD 回车，"
           "立即录2秒。录完停止手机外放。source.wav已存在则复用，不重复录音。\n"
           "录音只保存在板卡；已有0.5–2.5秒PCM WAV也可命名source.wav放本目录并跳过录音。"),
        code("source_path = replay_session.record_source()"),
        md("## 第3格：手机静音，连续完成三项\n"
           "先停止手机外放，恢复音响供电，保持箱体/接线位置不变。运行本格，"
           "现场就绪后输入 READY。每项配置完成后，只在准备听时输入 START，"
           "该项立即播放并采样约2.4秒，再自动静音。\n\n"
           "结束后输入：0无声、1清楚语音且结束安静、2杂音、3尖叫增长、4结束仍响。"
           "只有1继续，其他值停止。本轮不升增益。持续响声先断音响电源。\n\n"
           "结束后只下载最后显示路径的 summary.json。原始WAV/NPZ留板。"),
        code("result = replay_session.run_replay()"),
    ]
    nb = dict(cells=cells, metadata=dict(kernelspec=dict(display_name="Python 3",
                  language="python", name="python3"), language_info=dict(name="python")),
              nbformat=4, nbformat_minor=5)
    (DEST / "replay_trial.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1),
                                            encoding="utf-8", newline="\n")
    names = ["audio_replay.bit", "audio_replay.hwh", "replay_trial.py", "replay_tools.py",
             "replay_session.py", "closed_tools.py", "residual_tools.py", "replay_trial.ipynb", "README.md"]
    manifest = dict(schema_version=1, overlay="audio_replay", hardware_executed=False,
                    sample_rate_hz=48828.125, source_frames_max=131072,
                    source_format="signed16 -> signed24 << 8",
                    hashes={n: digest(DEST / n) for n in names},
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
