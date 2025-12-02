"""Generate additional analysis plots in a new folder.

Figures produced:
  01_timeseries_comparison_four.png        - Per-step queue length & completions (representative load)
  02_per_class_latency_comparison.png      - Boxplot / distribution of emergency vs normal latencies per scheduler
  03_completion_ratio_comparison.png       - Completion ratio across loads
  04_cdf_latency_comparison.png            - CDF of latencies per scheduler (representative load)
  05_requests_generated_vs_completed.png   - Generated vs completed across loads
  06_sla_compliance_analysis.png           - SLA-DWP-Fog admission vs emergency met vs miss rate across loads
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt

from config import SimulationConfig
from simulation import Simulation


OUT_DIR = Path("plots") / "extended"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOADS = [2,4,6,8,10,15,20,30,40,60,80,100]
SCHEDULERS = ["FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", "SLA-DWP-Fog"]


def run_sim(load: int, scheduler: str, sim_time: float = 120.0) -> Dict[str, object]:
    cfg = SimulationConfig(
        sim_time=sim_time,
        time_step=1.0,
        random_seed=2025,
        scheduler=scheduler,
        num_fog_nodes_x=1,
        num_fog_nodes_y=1,
        fog_cpu_capacity=20.0,
        fog_link_capacity=200.0,
        fog_max_queue_length=300,
        avg_requests_per_step=float(load),
        max_requests_per_step=max(200, 2*load),
        sla_window_TW=10.0,
        sla_J1_max=0.10,
        sla_J2_max_s=5.0,
        sla_J3_max=2.0,
        sla_eta1=0.02,
        sla_eta2=0.02,
        sla_eta3=0.02,
        sla_eps=1e-6,
    )
    return Simulation(cfg).run()


def ensure_font():
    plt.rcParams.update({
        "font.family": "Times New Roman",
        "figure.dpi": 300,
        "axes.grid": True,
        "grid.alpha": 0.25,
    })


def plot_timeseries(reports_rep_load: Dict[str, Dict[str, object]], load: int):
    ensure_font()
    fig, axes = plt.subplots(2, 1, figsize=(7,5), sharex=True)
    for sched, rep in reports_rep_load.items():
        q = rep.get("avg_queue_lengths", [])
        c = rep.get("per_step_completed", [])
        t = list(range(len(q)))
        axes[0].plot(t, q, label=sched, linewidth=1.4)
        axes[1].plot(t, c, label=sched, linewidth=1.4)
    axes[0].set_ylabel("Avg Queue Length")
    axes[1].set_ylabel("Completed / step")
    axes[1].set_xlabel("Time step")
    axes[0].legend(frameon=False, ncol=2)
    axes[1].legend(frameon=False, ncol=2)
    fig.suptitle(f"Scheduler Time Series (load={load})")
    fig.tight_layout(rect=[0,0,1,0.96])
    fig.savefig(OUT_DIR / "01_timeseries_comparison_four.png")
    plt.close(fig)


def plot_per_class_latency(reports: Dict[str, Dict[str, object]], load: int):
    ensure_font()
    fig, ax = plt.subplots(figsize=(7,4))
    data = []
    labels = []
    for sched, rep in reports.items():
        emer = rep.get("emergency_latencies", [])
        normal = rep.get("normal_latencies", [])
        if emer:
            data.append(emer)
            labels.append(f"{sched}\nEmergency")
        if normal:
            data.append(normal)
            labels.append(f"{sched}\nNormal")
    ax.boxplot(data, labels=labels, showfliers=False)
    ax.set_ylabel("Latency (s)")
    ax.set_title(f"Per-Class Latency Comparison (load={load})")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "02_per_class_latency_comparison.png")
    plt.close(fig)


def plot_completion_ratio_across_loads(all_reports: Dict[str, Dict[int, Dict[str, object]]]):
    ensure_font()
    fig, ax = plt.subplots(figsize=(6,4))
    for sched, per_load in all_reports.items():
        ratios = []
        for L in LOADS:
            rep = per_load[L]
            gen = rep.get("total_generated",0)
            comp = rep.get("total_completed",0)
            ratios.append((comp/gen) if gen else 0.0)
        ax.plot(LOADS, ratios, marker="o", linewidth=1.6, label=sched)
    ax.set_xlabel("Average requests per step")
    ax.set_ylabel("Completion Ratio")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "03_completion_ratio_comparison.png")
    plt.close(fig)


def plot_cdf_latencies(reports: Dict[str, Dict[str, object]], load: int):
    ensure_font()
    fig, ax = plt.subplots(figsize=(6,4))
    for sched, rep in reports.items():
        lats = sorted(rep.get("latencies", []))
        if not lats:
            continue
        y = [i/ (len(lats)-1) if len(lats)>1 else 1.0 for i in range(len(lats))]
        ax.plot(lats, y, linewidth=1.5, label=sched)
    ax.set_xlabel("Latency (s)")
    ax.set_ylabel("CDF")
    ax.set_title(f"Latency CDF (load={load})")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "04_cdf_latency_comparison.png")
    plt.close(fig)


def plot_generated_vs_completed(all_reports: Dict[str, Dict[int, Dict[str, object]]]):
    ensure_font()
    fig, ax = plt.subplots(figsize=(6,4))
    for sched, per_load in all_reports.items():
        gen_series = [per_load[L]["total_generated"] for L in LOADS]
        comp_series = [per_load[L]["total_completed"] for L in LOADS]
        ax.plot(LOADS, gen_series, linestyle="--", linewidth=1.2, label=f"{sched} generated")
        ax.plot(LOADS, comp_series, linestyle="-", linewidth=1.2, label=f"{sched} completed")
    ax.set_xlabel("Average requests per step")
    ax.set_ylabel("Count over simulation")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "05_requests_generated_vs_completed.png")
    plt.close(fig)


def plot_sla_compliance(all_reports: Dict[str, Dict[int, Dict[str, object]]]):
    ensure_font()
    fig, axes = plt.subplots(1,3, figsize=(12,4), sharex=True)
    sla_rep = all_reports.get("SLA-DWP-Fog", {})
    adm = [sla_rep[L]["total_admitted"]/sla_rep[L]["total_generated"] if sla_rep[L]["total_generated"] else 0.0 for L in LOADS]
    emerg = [sla_rep[L].get("emergency_met_rate",0.0) for L in LOADS]
    miss = [sla_rep[L].get("deadline_miss_rate",0.0) for L in LOADS]
    axes[0].plot(LOADS, adm, marker="o"); axes[0].set_ylabel("Admission Rate")
    axes[1].plot(LOADS, emerg, marker="s"); axes[1].set_ylabel("Emergency Met Rate")
    axes[2].plot(LOADS, miss, marker="^"); axes[2].set_ylabel("Deadline Miss Rate")
    for ax in axes:
        ax.set_xlabel("Avg reqs/step")
    fig.suptitle("SLA-DWP-Fog Compliance Metrics vs Load")
    fig.tight_layout(rect=[0,0,1,0.94])
    fig.savefig(OUT_DIR / "06_sla_compliance_analysis.png")
    plt.close(fig)


def main():
    # Run all loads for all schedulers (reuse results for multiple plots)
    all_reports: Dict[str, Dict[int, Dict[str, object]]] = {s:{} for s in SCHEDULERS}
    for sched in SCHEDULERS:
        for L in LOADS:
            all_reports[sched][L] = run_sim(L, sched)

    # Representative load for time-series & per-class (choose medium): 30
    rep_load = 30
    rep_reports = {s: all_reports[s][rep_load] for s in SCHEDULERS}
    plot_timeseries(rep_reports, rep_load)
    plot_per_class_latency(rep_reports, rep_load)
    plot_completion_ratio_across_loads(all_reports)
    plot_cdf_latencies(rep_reports, rep_load)
    plot_generated_vs_completed(all_reports)
    plot_sla_compliance(all_reports)

    # Save raw data
    with open(OUT_DIR / "extended_results.json", "w", encoding="utf-8") as f:
        json.dump(all_reports, f, indent=2)
    print(f"Extended plots saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
