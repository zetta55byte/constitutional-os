"""
runtime/visualization.py

Visualization of the governance-epistemic landscape:
  1. V(S) trajectory over time (Lyapunov descent)
  2. Basin map in 2D projection (V_drift × V_mem)
  3. Separatrix proximity over time
  4. A-safety theorem trace
  5. Phase portrait: recommendations vs verdicts

All plots saved as PNG. No GUI dependencies — matplotlib backend only.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class VisualizationConfig:
    output_dir:  str   = "output/figures"
    dpi:         int   = 150
    dark_mode:   bool  = True
    figsize:     tuple = (12, 7)


# ── Color palette (matches the cockpit / biology paper aesthetic) ─────────────
BLUE   = "#2563EB"
RED    = "#DC2626"
GREEN  = "#22C55E"
ORANGE = "#F97316"
PURPLE = "#7C3AED"
YELLOW = "#EAB308"
GRAY   = "#6B7280"
BG     = "#0D0E12"
SURF   = "#13151C"
BORDER = "#252836"
TEXT   = "#E2E4EF"


def _setup_dark(fig, axes):
    """Apply dark theme to figure."""
    fig.patch.set_facecolor(BG)
    for ax in (axes if hasattr(axes, '__iter__') else [axes]):
        ax.set_facecolor(SURF)
        ax.tick_params(colors=GRAY)
        ax.xaxis.label.set_color(TEXT)
        ax.yaxis.label.set_color(TEXT)
        ax.title.set_color(TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.grid(True, color=BORDER, linewidth=0.5, alpha=0.6)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# 1. V(S) TRAJECTORY — Lyapunov descent
# ══════════════════════════════════════════════════════════════════════════════

def plot_lyapunov_trajectory(
    records:  list[dict],   # list of {cycle, v, v_inv, v_mem, v_drift, v_rec, verdict, fixed}
    cfg:      VisualizationConfig = None,
    title:    str = "V(S) — Governance Energy Trajectory",
) -> str:
    """
    Plot V(S) over cycles, decomposed into components.
    Shows convergence toward attractor (V → 0).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    cfg = cfg or VisualizationConfig()
    _ensure_dir(cfg.output_dir)

    cycles  = [r["cycle"]   for r in records]
    v_total = [r["v"]       for r in records]
    v_inv   = [r.get("v_inv",   0) for r in records]
    v_mem   = [r.get("v_mem",   0) for r in records]
    v_drift = [r.get("v_drift", 0) for r in records]
    v_rec   = [r.get("v_rec",   0) for r in records]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=cfg.figsize,
                                    gridspec_kw={"height_ratios": [2, 1]})
    if cfg.dark_mode:
        _setup_dark(fig, [ax1, ax2])
        fig.suptitle(title, color=TEXT, fontsize=13, fontweight="bold")

    # Panel A: stacked V components
    ax1.fill_between(cycles, 0,        v_inv,
                     alpha=0.7, color=RED,    label=f"V_inv (invariants)  w=0.40")
    ax1.fill_between(cycles, v_inv,    [a+b for a,b in zip(v_inv, v_mem)],
                     alpha=0.7, color=ORANGE, label=f"V_mem (membranes)   w=0.25")
    ax1.fill_between(cycles,
                     [a+b for a,b in zip(v_inv, v_mem)],
                     [a+b+c for a,b,c in zip(v_inv, v_mem, v_drift)],
                     alpha=0.7, color=BLUE,  label=f"V_drift (forecast)  w=0.20")
    ax1.fill_between(cycles,
                     [a+b+c for a,b,c in zip(v_inv, v_mem, v_drift)],
                     v_total,
                     alpha=0.7, color=PURPLE, label=f"V_rec (recs)        w=0.15")

    # Total V line
    ax1.plot(cycles, v_total, color=TEXT, lw=2.5, label="V(S) total", zorder=5)

    # Fixed-point markers
    for r in records:
        if r.get("fixed"):
            ax1.axvline(r["cycle"], color=GREEN, lw=1.5, ls="--", alpha=0.6)

    # Attractor threshold line
    ax1.axhline(0.02, color=GREEN, lw=1.5, ls=":", alpha=0.8,
                label="Fixed-point threshold (0.02)")

    ax1.set_ylabel("V(S) — Governance Energy")
    ax1.set_ylim(0, max(max(v_total)*1.2, 0.1))
    ax1.legend(fontsize=9, loc="upper right",
               facecolor=SURF, edgecolor=BORDER, labelcolor=TEXT)

    # Panel B: verdict timeline
    verdict_colors = {
        "admitted":  GREEN,
        "deferred":  YELLOW,
        "blocked":   RED,
        "no_delta":  GRAY,
    }
    verdicts = [r.get("verdict", "no_delta") for r in records]
    for i, (c, v) in enumerate(zip(cycles, verdicts)):
        col = verdict_colors.get(v, GRAY)
        ax2.bar(c, 1, color=col, alpha=0.8, width=0.8)
        ax2.text(c, 0.5, v[:3].upper(), ha="center", va="center",
                 fontsize=8, color=BG, fontweight="bold")

    ax2.set_ylabel("G verdict")
    ax2.set_xlabel("Φ cycle")
    ax2.set_ylim(0, 1.2)
    ax2.set_yticks([])

    plt.tight_layout()
    path = os.path.join(cfg.output_dir, "lyapunov_trajectory.png")
    plt.savefig(path, dpi=cfg.dpi, bbox_inches="tight", facecolor=BG)
    plt.close()
    return path


# ══════════════════════════════════════════════════════════════════════════════
# 2. BASIN MAP — 2D projection of governance landscape
# ══════════════════════════════════════════════════════════════════════════════

def plot_basin_map(
    trajectory:  list[dict],   # list of {v_drift, v_mem, basin, cycle}
    cfg:         VisualizationConfig = None,
    title:       str = "Governance-Epistemic Landscape (V_drift × V_mem)",
) -> str:
    """
    2D projection of the attractor landscape.
    X axis: V_drift (epistemic drift)
    Y axis: V_mem (governance pressure)
    Shows basin boundaries, trajectory path, and separatrix.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    import numpy as np

    cfg = cfg or VisualizationConfig()
    _ensure_dir(cfg.output_dir)

    fig, ax = plt.subplots(figsize=cfg.figsize)
    if cfg.dark_mode:
        _setup_dark(fig, ax)
        fig.suptitle(title, color=TEXT, fontsize=13, fontweight="bold")

    # ── Basin regions ─────────────────────────────────────────────────────────
    x = np.linspace(0, 1, 300)
    y = np.linspace(0, 1, 300)
    X, Y = np.meshgrid(x, y)

    # Basin classification by V_drift × V_mem
    basin_map = np.zeros_like(X)
    basin_map[X < 0.05]                        = 0  # stable_governance
    basin_map[(X >= 0.05) & (Y < 0.2)]         = 1  # drifting_epistemic
    basin_map[(Y >= 0.2) & (X < 0.5)]          = 2  # governance_pressure
    basin_map[(X >= 0.5) | (Y >= 0.5)]         = 3  # critical_instability

    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([
        "#1a2e1a",   # stable_governance   → dark green
        "#1a1a2e",   # drifting_epistemic  → dark blue
        "#2e1a1a",   # governance_pressure → dark red
        "#2e2a1a",   # critical            → dark orange
    ])
    ax.contourf(X, Y, basin_map, levels=[-0.5, 0.5, 1.5, 2.5, 3.5],
                cmap=cmap, alpha=0.6)

    # ── Separatrix lines ──────────────────────────────────────────────────────
    ax.axvline(0.25, color=BLUE,   lw=2, ls="--", alpha=0.8,
               label="Epistemic separatrix (V_drift=0.25)")
    ax.axhline(0.20, color=RED,    lw=2, ls="--", alpha=0.8,
               label="Governance separatrix (V_mem=0.20)")
    ax.axvline(0.05, color=GREEN,  lw=1.5, ls=":", alpha=0.6,
               label="Attractor boundary (V_drift=0.05)")

    # ── Basin labels ──────────────────────────────────────────────────────────
    labels = [
        (0.025, 0.10, "STABLE\nGOVERNANCE", GREEN),
        (0.12,  0.10, "DRIFTING\nEPISTEMIC", BLUE),
        (0.12,  0.30, "GOVERNANCE\nPRESSURE", RED),
        (0.60,  0.60, "CRITICAL\nINSTABILITY", ORANGE),
    ]
    for lx, ly, txt, col in labels:
        ax.text(lx, ly, txt, ha="center", va="center", color=col,
                fontsize=8, fontweight="bold", alpha=0.9)

    # ── Trajectory path ───────────────────────────────────────────────────────
    if trajectory:
        tx = [r.get("v_drift", 0) for r in trajectory]
        ty = [r.get("v_mem",   0) for r in trajectory]

        # Gradient color along path
        for i in range(len(tx) - 1):
            t = i / max(len(tx) - 1, 1)
            col = (1-t) * np.array([0.34, 0.51, 0.93]) + \
                  t     * np.array([0.87, 0.45, 0.13])
            ax.plot(tx[i:i+2], ty[i:i+2], color=col, lw=2.5, alpha=0.9)

        # Start and end markers
        ax.scatter(tx[0],  ty[0],  color=GREEN,  s=120, zorder=6,
                   label="Start", marker="o")
        ax.scatter(tx[-1], ty[-1], color=ORANGE, s=150, zorder=6,
                   label="End",   marker="*")

        # Cycle labels
        for i, (px, py) in enumerate(zip(tx, ty)):
            ax.annotate(str(i+1), (px, py), textcoords="offset points",
                        xytext=(6, 4), fontsize=8, color=TEXT, alpha=0.8)

    ax.set_xlabel("V_drift  (epistemic drift)")
    ax.set_ylabel("V_mem  (governance pressure)")
    ax.set_xlim(0, 0.8)
    ax.set_ylim(0, 0.8)
    ax.legend(fontsize=8, loc="upper right",
              facecolor=SURF, edgecolor=BORDER, labelcolor=TEXT)

    plt.tight_layout()
    path = os.path.join(cfg.output_dir, "basin_map.png")
    plt.savefig(path, dpi=cfg.dpi, bbox_inches="tight", facecolor=BG)
    plt.close()
    return path


# ══════════════════════════════════════════════════════════════════════════════
# 3. SEPARATRIX PROXIMITY OVER TIME
# ══════════════════════════════════════════════════════════════════════════════

def plot_separatrix_proximity(
    records:  list[dict],   # {cycle, proximity, kappa, margin, boundary}
    cfg:      VisualizationConfig = None,
    title:    str = "Separatrix Proximity κ  (ridge curvature)",
) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    cfg = cfg or VisualizationConfig()
    _ensure_dir(cfg.output_dir)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(cfg.figsize[0], 6),
                                    gridspec_kw={"height_ratios": [2, 1]})
    if cfg.dark_mode:
        _setup_dark(fig, [ax1, ax2])
        fig.suptitle(title, color=TEXT, fontsize=13, fontweight="bold")

    cycles    = [r["cycle"]      for r in records]
    proximity = [r["proximity"]  for r in records]
    kappa     = [r["kappa"]      for r in records]
    at_risk   = [r.get("at_risk", False) for r in records]

    # Proximity
    ax1.plot(cycles, proximity, color=BLUE, lw=2.5, label="Proximity to separatrix")
    ax1.fill_between(cycles, proximity, alpha=0.15, color=BLUE)

    # Risk zone
    ax1.axhline(0.70, color=RED, lw=1.5, ls="--", alpha=0.8,
                label="At-risk threshold (0.70)")

    # Shade at-risk regions
    for i, (c, r) in enumerate(zip(cycles, at_risk)):
        if r:
            x0 = c - 0.5
            ax1.axvspan(x0, x0 + 1, alpha=0.15, color=RED)

    ax1.set_ylabel("Proximity  (0=deep attractor, 1=on separatrix)")
    ax1.set_ylim(0, 1.1)
    ax1.legend(fontsize=9, facecolor=SURF, edgecolor=BORDER, labelcolor=TEXT)

    # Ridge curvature κ
    ax2.bar(cycles, kappa, color=[RED if r else BLUE for r in at_risk],
            alpha=0.8, width=0.7)
    ax2.set_ylabel("κ  (ridge curvature)")
    ax2.set_xlabel("Φ cycle")

    plt.tight_layout()
    path = os.path.join(cfg.output_dir, "separatrix_proximity.png")
    plt.savefig(path, dpi=cfg.dpi, bbox_inches="tight", facecolor=BG)
    plt.close()
    return path


# ══════════════════════════════════════════════════════════════════════════════
# 4. MULTI-PROFILE HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

def plot_profile_heatmap(
    profile_records: dict[str, list[dict]],   # profile_id → [{cycle, v, basin}]
    cfg:             VisualizationConfig = None,
    title:           str = "Profile Risk Heatmap",
) -> str:
    """
    Heatmap of V(S) per profile over time.
    Rows = profiles, columns = cycles.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    cfg = cfg or VisualizationConfig()
    _ensure_dir(cfg.output_dir)

    if not profile_records:
        return ""

    profiles = list(profile_records.keys())
    n_cycles = max(len(v) for v in profile_records.values())
    matrix   = np.full((len(profiles), n_cycles), np.nan)

    for i, pid in enumerate(profiles):
        for j, rec in enumerate(profile_records[pid]):
            matrix[i, j] = rec.get("v", 0)

    fig, ax = plt.subplots(figsize=cfg.figsize)
    if cfg.dark_mode:
        _setup_dark(fig, ax)
        fig.suptitle(title, color=TEXT, fontsize=13, fontweight="bold")

    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn_r",
                   vmin=0, vmax=0.6, interpolation="nearest")

    # Labels
    ax.set_yticks(range(len(profiles)))
    ax.set_yticklabels(profiles, color=TEXT, fontsize=9)
    ax.set_xlabel("Φ cycle", color=TEXT)
    ax.set_xticks(range(n_cycles))
    ax.set_xticklabels([str(i+1) for i in range(n_cycles)], color=GRAY, fontsize=8)

    # Value annotations
    for i in range(len(profiles)):
        for j in range(n_cycles):
            if not np.isnan(matrix[i, j]):
                ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center",
                        fontsize=7, color="white" if matrix[i,j] > 0.3 else "black")

    plt.colorbar(im, ax=ax, label="V(S)", shrink=0.8)
    plt.tight_layout()
    path = os.path.join(cfg.output_dir, "profile_heatmap.png")
    plt.savefig(path, dpi=cfg.dpi, bbox_inches="tight", facecolor=BG)
    plt.close()
    return path


# ══════════════════════════════════════════════════════════════════════════════
# 5. FULL LANDSCAPE REPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_landscape_report(
    records:  list[dict],
    cfg:      VisualizationConfig = None,
) -> dict[str, str]:
    """Generate all visualization figures and return paths."""
    cfg = cfg or VisualizationConfig()
    paths = {}

    try:
        paths["lyapunov"]   = plot_lyapunov_trajectory(records, cfg)
    except Exception as e:
        print(f"[viz] lyapunov failed: {e}")

    try:
        paths["basin_map"]  = plot_basin_map(records, cfg)
    except Exception as e:
        print(f"[viz] basin_map failed: {e}")

    try:
        paths["separatrix"] = plot_separatrix_proximity(records, cfg)
    except Exception as e:
        print(f"[viz] separatrix failed: {e}")

    return paths
