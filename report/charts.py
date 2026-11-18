from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

KOREAN_FONTS = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR"]


def _set_korean_font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    for f in KOREAN_FONTS:
        if f in names:
            plt.rcParams["font.family"] = f
            break
    plt.rcParams["axes.unicode_minus"] = False


def quadrant_chart(r: dict, path: Path) -> Path:
    """x = 관심도, y = 호감도, 점 크기 = 언급 수, 색 = 논란도."""
    _set_korean_font()
    ms = r["members"]
    x = [m["interest"] for m in ms]
    y = [m["favor"] for m in ms]
    size = [max(40, min(800, m["n"] ** 0.5 * 12)) for m in ms]
    color = [m["controversy"] for m in ms]
    fig, ax = plt.subplots(figsize=(7, 6), dpi=150)
    sc = ax.scatter(x, y, s=size, c=color, cmap="coolwarm", vmin=0, vmax=0.6, edgecolor="black", linewidth=0.5)
    for m, xi, yi in zip(ms, x, y):
        ax.annotate(m["name"], (xi, yi), textcoords="offset points", xytext=(8, 6), fontsize=10)
    xm = sorted(x)[len(x) // 2]
    ym = sorted(y)[len(y) // 2]
    ax.axvline(xm, color="gray", lw=0.8, ls="--")
    ax.axhline(ym, color="gray", lw=0.8, ls="--")
    ax.set_xlabel("관심도 (긍정+부정 반응량)")
    ax.set_ylabel("호감도 (긍정)")
    ax.set_title(f"{r['group_name']} 멤버 호감도 × 관심도 (최근 {r['days']}일)")
    fig.colorbar(sc, ax=ax, label="논란도")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
