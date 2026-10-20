"""A-owned prerecorded-source session. Imports never access hardware."""
import hashlib
import json
import time
import uuid
from pathlib import Path

from closed_tools import trial_parameters
from replay_tools import RATE, prepare_source
from residual_tools import load_candidate

HERE = Path(__file__).resolve().parent


def check_package():
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["hashes"].items():
        path = HERE / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("软件包缺失或版本不匹配：" + str(path))
    print("REPLAY_PACKAGE_OK; NO_AUDIO_STARTED", flush=True)
    return manifest


def _mute_codec():
    import os
    import fcntl
    fd = os.open("/dev/i2c-1", os.O_RDWR)
    try:
        fcntl.ioctl(fd, 0x0703, 0x3B)
        for addr, val in ((0x401C, 0), (0x401E, 0), (0x4023, 0xE5), (0x4024, 0xE5)):
            payload = addr.to_bytes(2, "big") + bytes([val])
            if os.write(fd, payload) != len(payload):
                raise IOError("Codec mute write incomplete")
    finally:
        os.close(fd)


def record_source(path=None, ask=input):
    """Record two seconds on the board; speakers must be physically powered off."""
    check_package()
    path = HERE / "source.wav" if path is None else Path(path)
    if path.exists():
        print("已有录音，保留并复用：" + str(path))
        return path
    from pynq.overlays.base import BaseOverlay
    audio = BaseOverlay("base.bit").audio
    try:
        audio.configure()
        _mute_codec()
        audio.select_line_in()
        if ask("音响已断电；箱盖位置不变；手机循环语音已播放。输入 RECORD 立即录2秒：").strip().upper() != "RECORD":
            print("已取消录音。")
            return None
        print("录音中：2秒。", flush=True)
        audio.record(2)
        audio.save(str(path))
    finally:
        try:
            audio.deselect_inputs()
        finally:
            _mute_codec()
    print("录音完成。现在停止手机外放。录音只保存在板卡：" + str(path), flush=True)
    return path


def load_scene(path):
    scene = json.loads(Path(path).read_text(encoding="utf-8"))
    if (scene.get("schema_version") != 1 or
            scene.get("fixture_id") != "box_v1_20261016" or
            scene.get("calibration_match_original") is not True or
            scene.get("operator_verified") is not True or
            scene.get("codec_hp_volume") != 40 or
            scene.get("sample_rate_hz") != RATE or
            scene.get("wiring", {}).get("channel_mapping_verified") is not True or
            scene.get("speaker", {}).get("external_volume_control_verified") is not True):
        raise ValueError("现场配置不完整或不匹配原标定，不能发声：" + str(path))
    for group, names in (
            ("wiring", ("max4466_supply_v", "max4466_gain_setting")),
            ("box", ("dimensions_cm", "lid_state")),
            ("microphone", ("position_xyz_cm", "orientation")),
            ("speaker", ("position_xyz_cm", "orientation"))):
        if any(scene.get(group, {}).get(k) in (None, "", []) for k in names):
            raise ValueError("配置缺项：" + group)
    if not isinstance(scene.get("operator_notes"), str) or not scene["operator_notes"].strip():
        raise ValueError("operator_notes需填写现场说明")
    return scene


def run_replay(source_path=None, setup_path=None, model_path=None,
               output_root=None, ask=input, runner=None, verify_package=True):
    """One direct-source audibility trial, then one fixed-gain A/B pair.

    Only ask before a trial, while the codec is muted. No runtime input is an
    emergency stop. The PL bounds each trial independently of this Python process.
    """
    source_path = HERE / "source.wav" if source_path is None else Path(source_path)
    setup_path = HERE.parent / "audio_closed/field_setup.json" if setup_path is None else Path(setup_path)
    model_path = HERE.parent / "audio_calibrate/candidate_box_v1_256.json" if model_path is None else Path(model_path)
    output_root = HERE / "replay_results" if output_root is None else Path(output_root)
    folder = output_root / ("replay_" + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True, exist_ok=False)
    state = dict(schema_version=1, run_id=folder.name, status="preflight",
                 trials=[], stage="package", sound_seconds_completed=0,
                 normal_playback_heard=False, normal_mic_amplification_demonstrated=False,
                 interpretation="digital-source acoustic feedback comparison; no measured MSG/ASG")
    started = time.monotonic()

    def save():
        state["wall_elapsed_seconds"] = time.monotonic() - started
        temp = folder / "summary.json.tmp"
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(folder / "summary.json")

    try:
        save()
        if verify_package:
            check_package()
        state["stage"] = "scene"
        scene = load_scene(setup_path)
        state.update(setup=scene, setup_sha256=hashlib.sha256(setup_path.read_bytes()).hexdigest(),
                     stimulus="board WAV; phone OFF during all playback",
                     model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest())
        state["stage"] = "prepare_source"
        _, q = load_candidate(model_path, scene["fixture_id"], 40, RATE)
        gain_q12, _ = trial_parameters(-35.0, 2)
        pcm, source_info = prepare_source(source_path, q, gain_q12)
        # Final ring is deliberately the silent-source decay tail; not full audio.
        seconds = len(pcm) / RATE + .4
        state.update(source=source_info, feedback_gain_db_requested=-35.0,
                     feedback_gain_q12=gain_q12, seconds_per_trial=seconds,
                     planned_max_sound_seconds=3*seconds,
                     capture_scope="last 16384 frames only; source-off decay tail")
        print("手机保持静音。3项：直放确认、旁路、抵消；每项%.2f秒，总发声最多%.2f秒。" %
              (seconds, 3*seconds), flush=True)
        print("反馈增益−35 dB；录音注入峰值%.2f dBFS（两模式完全相同）。" %
              source_info["source_peak_dbfs"], flush=True)
        if runner is None:
            from replay_trial import replay_trial
            runner = replay_trial
        state["stage"] = "scene_confirmation"
        save()
        if ask("手机已停止外放、音响已恢复供电且能立即断电、夹具未动、同意板卡本地采样：输入 READY：").strip().upper() != "READY":
            state.update(status="cancelled", stop_reason="scene_not_confirmed")
            return state
        state["status"] = "running"
        pair = []
        for index, (name, bypass, direct) in enumerate(
                (("direct", True, True), ("bypass", True, False), ("cancel", False, False)), 1):
            state["stage"] = name
            row = dict(index=index, mode=name, status="preparing")
            state["trials"].append(row)
            save()

            def ready():
                print("[%d/3] %s 配置完成，当前静音。" % (index, name), flush=True)
                if ask("输入 START：立即播放并采样%.2f秒；其他输入停止：" % seconds).strip().upper() != "START":
                    return False
                row["status"] = "audio_authorized"
                save()
                return True

            metadata = runner(folder / ("%02d_%s.npz" % (index, name)),
                              scene["fixture_id"], str(model_path), pcm,
                              bypass=bypass, direct_only=direct, gain_db=-35.0,
                              seconds=seconds, hp_volume=40, speaker_confirmed=True,
                              local_capture_confirmed=True, before_start=ready)
            row["metadata"] = metadata
            row["status"] = "complete"
            state["sound_seconds_completed"] += metadata["sound_seconds_nominal"]
            save()
            if (not metadata.get("verification", {}).get("bit_exact") or
                    any(metadata.get(k, 0) for k in ("prediction_saturations",
                        "residual_saturations", "gain_saturations", "mix_saturations",
                        "mic_full_scale_samples"))):
                raise RuntimeError("数字核对或饱和检查失败，停止后续项目")
            if (metadata.get("model_sha256") != state["model_sha256"] or
                    metadata.get("source_pcm16_sha256") != source_info["pcm16_sha256"] or
                    metadata.get("bypass") is not bypass or
                    metadata.get("gain_q12") != (0 if direct else gain_q12) or
                    metadata.get("hp_volume") != 40):
                raise RuntimeError("试验实值与计划不一致")
            answer = ask("已结束。听感：0无声 / 1清楚语音且结束安静 / 2杂音 / 3尖叫增长 / 4结束仍响：").strip()
            row["hearing"] = {"0": "inaudible", "1": "speech", "2": "noise",
                              "3": "howl_or_growth", "4": "not_quiet"}.get(answer, "operator_stop")
            save()
            if answer != "1":
                state.update(status="stopped", stop_reason=name + ":" + row["hearing"])
                return state
            if direct:
                state["normal_playback_heard"] = True
            else:
                pair.append(metadata)
        keys = ("bit_sha256", "model_sha256", "coefficients_sha256", "source_pcm16_sha256",
                "gain_q12", "hp_volume", "sample_rate_hz", "completed_frames", "fixture_id")
        if any(pair[0].get(k) != pair[1].get(k) for k in keys):
            raise RuntimeError("旁路/抵消配置不一致")
        state.update(status="completed", pair_configuration_matches=True,
                     conclusion="已测−35 dB两模式均听到语音且结束安静；未找到旁路失稳阈值，不能量化ASG")
    except (Exception, KeyboardInterrupt) as exc:
        state.update(status="stopped", stop_reason=type(exc).__name__ + ": " + str(exc))
        if state["trials"] and state["trials"][-1]["status"] in ("preparing", "audio_authorized"):
            state["sound_seconds_unknown_for_failed_trial"] = (
                state["trials"][-1]["status"] == "audio_authorized")
            state["trials"][-1]["status"] = "interrupted_or_failed"
        print("停止阶段：" + state["stage"] + "；原因：" + state["stop_reason"], flush=True)
    finally:
        save()
        print("结束。返回这个文件：" + str(folder / "summary.json"), flush=True)
        print("原始WAV/NPZ留在板卡。", flush=True)
    return state
