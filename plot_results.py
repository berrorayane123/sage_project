# ===== plot_results.py: turns results.csv into figures for the slides =====
# Run AFTER evaluate.py.   Needs:  pip install matplotlib
import csv
import matplotlib.pyplot as plt

SURFACE, TEXT, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
OURS, OTHER = "#2a78d6", "#b9b8b2"                       # highlight our method, others in gray
BLUES = ["#e8f1fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#104281"]

METHODS = ["sage", "ledger", "ledger+confidence", "ledger+domino", "always_confirm", "ours"]
NAMES = {"sage":  "SAGE-style baseline", "ledger": "+ Ledger", "ledger+confidence": "+ Ledger + Confidence",
         "ledger+domino": "+ Ledger + Domino", "always_confirm": "Always confirm", "ours": "OURS (full)"}
REVISE = ["revise_sure", "revise_prefer", "revise_unsure_new", "revise_unsure_old", "retract", "domino"]
TYPE_NAMES = ["Sure", "Prefer", "Unsure\n(new)", "Unsure\n(old)", "Forget it", "Domino"]

rows = list(csv.DictReader(open("results.csv", encoding="utf-8")))

def pct(method, kinds, key="correct"):
    r = [x for x in rows if x["method"] == method and x["kind"] in kinds]
    return 100 * sum(int(x[key]) for x in r) / len(r)

def avg_q(method, kinds):
    r = [x for x in rows if x["method"] == method and x["kind"] in kinds]
    return sum(int(x["questions"]) for x in r) / len(r)

def style(ax, fig):
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


# ---------- Figure 1: correct calls when the user changes their mind ----------
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
style(ax, fig)
values = [pct(m, REVISE) for m in METHODS]
colors = [OURS if m == "ours" else OTHER for m in METHODS]
bars = ax.barh([NAMES[m] for m in METHODS], values, color=colors, height=0.6)
ax.invert_yaxis()
ax.set_xlim(0, 112)
ax.xaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for bar, v in zip(bars, values):
    ax.text(v + 1.5, bar.get_y() + bar.get_height() / 2, f"{v:.0f}%", va="center", color=TEXT, fontsize=10)
ax.set_xlabel("Correct final tool call (%)", color=MUTED)
ax.set_title("When the user changes their mind (162 conversations, ClarifyBench-Revise)",
             loc="left", color=TEXT, fontsize=11, pad=12)
plt.tight_layout()
plt.savefig("fig1_correct.png", facecolor=SURFACE)
plt.close()


# ---------- Figure 2: where each version fails (heatmap) ----------
fig, ax = plt.subplots(figsize=(9, 4.4), dpi=200)
style(ax, fig)
ax.spines["bottom"].set_visible(False)
grid = [[pct(m, [k]) for k in REVISE] for m in METHODS]
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list("blues", BLUES)
ax.imshow(grid, cmap=cmap, vmin=0, vmax=100, aspect="auto")
ax.set_xticks(range(len(REVISE)), TYPE_NAMES, color=MUTED, fontsize=9)
ax.set_yticks(range(len(METHODS)), [NAMES[m] for m in METHODS], color=MUTED, fontsize=9)
ax.tick_params(top=False, bottom=False, labeltop=True, labelbottom=False)
for i in range(len(METHODS)):
    for j in range(len(REVISE)):
        v = grid[i][j]
        ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=9,
                color="white" if v >= 60 else TEXT)
ax.set_xticks([x - 0.5 for x in range(1, len(REVISE))], minor=True)
ax.set_yticks([y - 0.5 for y in range(1, len(METHODS))], minor=True)
ax.grid(which="minor", color=SURFACE, linewidth=2)
ax.tick_params(which="minor", length=0)
ax.set_title("Correct calls by type of change (27 conversations per cell)", loc="left", color=TEXT, fontsize=11, pad=28)
plt.tight_layout()
plt.savefig("fig2_by_type.png", facecolor=SURFACE)
plt.close()


# ---------- Figure 3: correctness vs. number of questions ----------
fig, ax = plt.subplots(figsize=(7, 4.6), dpi=200)
style(ax, fig)
ax.spines["left"].set_visible(True)
ax.spines["left"].set_color(GRID)
ax.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for m in METHODS:
    x, y = avg_q(m, REVISE), pct(m, REVISE)
    is_ours = m == "ours"
    ax.scatter(x, y, s=110 if is_ours else 70, color=OURS if is_ours else OTHER,
               edgecolors=SURFACE, linewidths=2, zorder=3)
    offsets = {"ours": (-10, 10, "right"), "always_confirm": (8, -14, "left"),
               "ledger+domino": (-10, 8, "right"), "ledger+confidence": (8, -14, "left")}
    dx, dy, ha = offsets.get(m, (8, -4, "left"))
    ax.annotate(NAMES[m], (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha,
                fontsize=9, color=TEXT if is_ours else MUTED, fontweight="bold" if is_ours else "normal")
ax.set_xlim(1, 4.3)
ax.set_ylim(-5, 108)
ax.set_xlabel("Average questions asked per conversation (fewer is better)", color=MUTED)
ax.set_ylabel("Correct final call (%)", color=MUTED)
ax.set_title("Accuracy vs. questions: best = top-left", loc="left", color=TEXT, fontsize=11, pad=12)
plt.tight_layout()
plt.savefig("fig3_tradeoff.png", facecolor=SURFACE)
plt.close()


# ---------- Figure 4: the results table as an image (for slides) ----------
header = ["Version", "Correct", "Stale value", "Exec. error", "Broken", "Avg. questions"]
table = [[NAMES[m], f"{pct(m, REVISE):.1f}%", f"{pct(m, REVISE, 'stale'):.1f}%",
          f"{pct(m, REVISE, 'exec_error'):.1f}%", f"{pct(m, REVISE, 'broken'):.1f}%",
          f"{avg_q(m, REVISE):.2f}"] for m in METHODS]
fig, ax = plt.subplots(figsize=(9, 3), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.axis("off")
t = ax.table(cellText=table, colLabels=header, loc="center", cellLoc="center", colLoc="center")
t.auto_set_font_size(False)
t.set_fontsize(10)
t.scale(1, 1.7)
for r in range(len(METHODS) + 1):
    t[r, 0].set_width(0.26)                                # wider first column
for (r, c), cell in t.get_celld().items():
    cell.set_edgecolor(GRID)
    cell.set_facecolor(SURFACE)
    cell.get_text().set_color(TEXT)
    if r == 0:
        cell.get_text().set_fontweight("bold")
        cell.get_text().set_color(MUTED)
    if r == len(METHODS):                                  # the "ours" row
        cell.set_facecolor("#e8f1fd")
        cell.get_text().set_fontweight("bold")
ax.set_title("Results on the 162 revision conversations (ClarifyBench-Revise)", color=TEXT, fontsize=11, loc="left")
plt.tight_layout()
plt.savefig("fig4_table.png", facecolor=SURFACE)
plt.close()

print("Saved: fig1_correct.png, fig2_by_type.png, fig3_tradeoff.png, fig4_table.png")
