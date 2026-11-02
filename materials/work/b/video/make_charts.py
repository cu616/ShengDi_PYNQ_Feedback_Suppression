"""生成视频用的两张数据图（1920×1080 PNG + 可编辑 SVG）。

只用已有证据，不新造数字：
  图 1  322 Hz 同条件三臂对照 —— 10-28 那轮实测（A 的 evidence.json）
  图 2  模型对不对决定成败 —— 独立验证段 300–460 Hz 带内抑制（本轮 cases.json）

两张都标了条件与出处。图 1 的数字在 A 的 script.md 里标了 [C 定稿]，正式上字幕前等 C 确认；
图 2 是 B 侧可复现的离线量，明确写"预测抑制，不是整机抗啸叫"。

用法：python materials/work/b/video/make_charts.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "materials/work/b/video"

INK = "#1f2933"
MUTED = "#5b6672"
GRID = "#dfe3e8"
BLUE = "#2f7ed8"
ORANGE = "#e8833a"
GREEN = "#2e9e6b"
GREY = "#9aa5b1"

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "PingFang SC", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": "#f6f7f9",
    "axes.facecolor": "#f6f7f9",
    "savefig.facecolor": "#f6f7f9",
    "text.color": INK,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
})


def fig1_three_arm():
    """322 Hz 三臂：同一摆位、同一增益，只改抵消配置。"""
    arms = ["无环路\n（数字增益置 0）", "环路闭合\n未抵消", "环路闭合\n已抵消"]
    vals = [45.44, 49.19, 44.43]
    colors = [GREY, ORANGE, BLUE]
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=150)
    bars = ax.bar(arms, vals, color=colors, width=0.5, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.35, f"{v:.2f}",
                ha="center", va="bottom", fontsize=20, color=INK, fontweight="bold")
    ax.set_ylim(40, 52)
    ax.set_xlim(-0.6, 3.05)
    ax.set_ylabel("麦克风端 322 Hz 电平（dB，同一参考）", fontsize=17)
    ax.grid(axis="y", color=GRID, linewidth=1.2, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(axis="x", labelsize=16, length=0)
    ax.tick_params(axis="y", labelsize=14)

    # 三个派生量，直接写在图上
    ax.annotate("", xy=(1.32, 49.19), xytext=(1.32, 45.44),
                arrowprops=dict(arrowstyle="<->", color=ORANGE, lw=2))
    ax.text(1.40, 47.3, "环路提升\n3.75 dB", fontsize=15, color="#b5651d", va="center")
    ax.annotate("", xy=(2.32, 44.43), xytext=(2.32, 49.19),
                arrowprops=dict(arrowstyle="<->", color=BLUE, lw=2))
    ax.text(2.40, 46.8, "声学差\n4.76 dB", fontsize=15, color="#245f9f", va="center")

    fig.suptitle("322 Hz 单频、同摆位、同增益（−8 dB）下的三臂对照",
                 fontsize=24, fontweight="bold", x=0.06, ha="left", y=0.965)
    fig.text(0.06, 0.875,
             "声学差 = 环路提升 + 过冲（4.76 = 3.75 + 1.01）。单频、单摆位的结论，不能外推为整机抗啸叫。",
             fontsize=15, color=MUTED, ha="left")
    fig.text(0.06, 0.045,
             "出处：2026-10-28 宽残差 v3 实测（A 的 evidence.json#steady_state_tone_three_point）。"
             "数字上字幕前等 C 定稿。",
             fontsize=12, color=GREY, ha="left")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.80, bottom=0.16)
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"fig-data-1-three-arm.{ext}")
    plt.close(fig)


def fig2_model_quality():
    """同一份独立验证数据，换不同模型：模型对不对决定成败。"""
    labels = ["本轮重拟合", "已部署模型", "旧夹具模型", "全零系数"]
    vals = [4.17, 4.21, -4.40, 0.00]
    colors = [GREEN, GREEN, ORANGE, GREY]
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=150)
    bars = ax.barh(labels, vals, color=colors, height=0.5, zorder=3)
    for b, v in zip(bars, vals):
        off = 0.14 if v > 0 else (-0.14 if v < 0 else 0.14)
        ax.text(v + off, b.get_y() + b.get_height() / 2, f"{v:+.2f} dB",
                va="center", ha="left" if v >= 0 else "right",
                fontsize=20, color=INK, fontweight="bold")
    ax.axvline(0, color=MUTED, linewidth=1.6, zorder=4)
    ax.axvline(0.5, color=BLUE, linewidth=1.6, linestyle="--", zorder=2)
    ax.text(0.62, -0.48, "通过线 +0.5 dB", color="#245f9f", fontsize=14,
            va="bottom", ha="left", clip_on=False)
    ax.set_xlim(-7, 7)
    ax.set_xlabel("300–460 Hz 带内时域抑制（dB，正=残差变小）", fontsize=17)
    ax.grid(axis="x", color=GRID, linewidth=1.2, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", labelsize=17, length=0)
    ax.tick_params(axis="x", labelsize=14)
    ax.invert_yaxis()          # 让"本轮重拟合"在最上，读者先看好模型

    fig.suptitle("同一份独立验证数据，换不同的模型", fontsize=24, fontweight="bold",
                 x=0.06, ha="left", y=0.965)
    fig.text(0.06, 0.885,
             "模型对，残差变小；模型错（旧布置的模型）残差反而变大 4.4 dB。"
             "这就是换摆位必须重标定的原因。",
             fontsize=15, color=MUTED, ha="left")
    fig.text(0.06, 0.070,
             "口径：独立验证段（bind4 第 5、6 段）上的预测残差，属于离线预测抑制，"
             "不是整机抗啸叫、不是 ASG、不是听感。",
             fontsize=12, color=GREY, ha="left")
    fig.text(0.06, 0.032, "出处：report/verification/recalibration-algorithm-2026-11-01/cases.json",
             fontsize=12, color=GREY, ha="left")
    fig.subplots_adjust(left=0.16, right=0.97, top=0.79, bottom=0.17)
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"fig-data-2-model-quality.{ext}")
    plt.close(fig)


if __name__ == "__main__":
    fig1_three_arm()
    fig2_model_quality()
    for p in sorted(OUT.glob("fig-data-*")):
        print(p.name, p.stat().st_size // 1024, "KB")
