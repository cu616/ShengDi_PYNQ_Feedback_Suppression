"""标定激励生成：按 RMS 定档，并显式声明可达上限。

这个文件存在的原因是一条实测事实（2026-11-01 队长指出，B 复核确认）：
    `board/audio_replay/pick_excitation_level.sh` 请求 -13.3 / -7.3 / -4.3 dBFS 三档，
    三档在 `PEAK_CAP=0.80` 处**全部被削到同一峰值**，`rint(x*32767)` 之后是同一份 PCM。
    一个"电平扫描"扫的是同一个数组，等于报了三次尝试、只测了一个条件。

这里强制三条：
  1. 激励按**目标 RMS** 归一，不按峰值归一；
  2. 峰值上限只用来判**可达性**，不用来静默改电平：目标不可达时返回 `ok=False`
     并给出可达上限，而不是削顶后当成"这一档"；
  3. 返回值里带**实测** RMS、实测峰值和 PCM 摘要，调用方可以自己证明两档是不是两个数组。

为什么不"削顶后重新归一"：削顶会引入谐波，谐波在时域最小二乘里是**与参考不相关的能量**，
会让拟合在削顶频点上系统性偏低。声反馈辨识里这个偏差不可接受，宁可降档。
"""
from __future__ import annotations

import hashlib

import numpy as np

# 满幅 = 1.0；int16 编码时 32767 对应 1.0。
INT16_FULL = 32767.0
DEFAULT_SEED = 4242
DEFAULT_PEAK_CAP = 0.80


def crest_factor_db(frames, seed=DEFAULT_SEED):
    """该 seed/长度下高斯白噪的峰值因数（dB）。用来算可达上限，不参与电平设定。"""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(int(frames))
    x -= x.mean()
    rms = float(np.sqrt(np.mean(x ** 2))) or 1.0
    return float(20 * np.log10(np.max(np.abs(x)) / rms))


def reachable_level_db(frames, seed=DEFAULT_SEED, peak_cap=DEFAULT_PEAK_CAP):
    """在峰值上限下，这个 seed/长度**能真实达到**的最高 RMS 电平（dBFS）。"""
    return float(20 * np.log10(peak_cap) - crest_factor_db(frames, seed))


def white_noise_pcm16(level_db, frames, seed=DEFAULT_SEED, peak_cap=DEFAULT_PEAK_CAP):
    """生成 int16 白噪，返回 (pcm, record)。目标不可达时 record['ok'] 为 False，pcm 为 None。

    record 字段：
      ok / level_db_commanded / level_db_actual / rms_db_actual / peak_linear /
      peak_dbfs / crest_db / reachable_db / sha256 / frames / seed / peak_cap
    """
    frames = int(frames)
    if frames < 1024:
        raise ValueError('frames must be >= 1024 so the crest factor is meaningful')
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(frames)
    x -= x.mean()                       # 去直流：直流会被拟合当成路径增益
    rms0 = float(np.sqrt(np.mean(x ** 2))) or 1.0
    x /= rms0

    crest_db = crest_factor_db(frames, seed)
    ceiling_db = float(20 * np.log10(peak_cap) - crest_db)
    target = float(10 ** (float(level_db) / 20.0))
    peak_needed = target * 10 ** (crest_db / 20.0)

    record = {
        'frames': frames, 'seed': int(seed), 'peak_cap': float(peak_cap),
        'level_db_commanded': float(level_db),
        'crest_db': crest_db, 'reachable_db': ceiling_db,
        'peak_needed': float(peak_needed),
    }
    if peak_needed > peak_cap * (1 + 1e-12):
        # 不可达：不削、不降档、不假装。让调用方决定是否改用可达档位。
        record.update({'ok': False, 'reason': 'level unreachable under peak cap',
                       'suggest_level_db': ceiling_db, 'pcm': None})
        return None, record

    x *= target
    pcm = np.rint(x * INT16_FULL).astype(np.int16)
    # 量化后的实测值才是真值：int16 的 ±0.5 LSB 会改一点 RMS，尤其在小电平上。
    y = pcm.astype(np.float64) / INT16_FULL
    rms_actual = float(np.sqrt(np.mean(y ** 2)))
    record.update({
        'ok': True, 'pcm': pcm,
        'level_db_actual': float(20 * np.log10(max(rms_actual, 1e-12))),
        'rms_db_actual': float(20 * np.log10(max(rms_actual, 1e-12))),
        'peak_linear': float(np.max(np.abs(y))),
        'peak_dbfs': float(20 * np.log10(max(float(np.max(np.abs(y))), 1e-12))),
        'sha256': hashlib.sha256(pcm.tobytes()).hexdigest(),
        'quantisation_error_db': float(20 * np.log10(max(rms_actual, 1e-12)) - float(level_db)),
    })
    return pcm, record


def check_distinct(records):
    """校验一组电平档确实生成了互不相同的 PCM。返回 (ok, 重复分组)。

    这是"相同 PCM 不能当多个档位"这条规则的机器执行点：比较的是 int16 字节流的摘要，
    不是标称电平，也不是峰值。
    """
    seen, groups = {}, {}
    for rec in records:
        if not rec.get('ok'):
            continue
        sha = rec['sha256']
        if sha in seen:
            groups.setdefault(sha, [seen[sha]]).append(rec['level_db_commanded'])
        else:
            seen[sha] = rec['level_db_commanded']
    return (not groups), groups
