import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt

from config import SimulationConfig
from simulation import Simulation


PLOTS_DIR = Path("plots") / "comparison"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def pctl(values: List[float], q: float) -> float | None:
    if not values:
        return None
    arr = sorted(values)
    k = (len(arr) - 1) * q
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return arr[f]
    d0 = arr[f] * (c - k)
    d1 = arr[c] * (k - f)
    return d0 + d1


def run_grid(loads: List[int], schedulers: List[str]) -> Dict[str, Dict[int, Dict[str, float]]]:
    results: Dict[str, Dict[int, Dict[str, float]]] = {}
    for sched in schedulers:
        results[sched] = {}
        for load in loads:
            cfg = SimulationConfig(
                sim_time=120.0,
                time_step=1.0,
                random_seed=2025,
                scheduler=sched,
                num_fog_nodes_x=1,
                num_fog_nodes_y=1,
                fog_cpu_capacity=20.0,
                fog_link_capacity=200.0,
                fog_max_queue_length=300,
                avg_requests_per_step=float(load),
                max_requests_per_step=max(200, 2 * load),
                sla_window_TW=10.0,
                sla_J1_max=0.10,
                sla_J2_max_s=5.0,
                sla_J3_max=2.0,
                sla_eta1=0.02,
                sla_eta2=0.02,
                sla_eta3=0.02,
                sla_eps=1e-6,
            )
            rep = Simulation(cfg).run()
            # Compute metrics for plotting
            latencies = rep.get("latencies", [])
            mean_lat = rep.get("avg_latency")
            p95 = pctl(latencies, 0.95)
            overall_miss = 1.0 - float(rep.get("overall_deadline_met_rate", 0.0))
            emer_met = float(rep.get("priority3_deadline_met_rate", 0.0))
            adm_rate = (rep["total_admitted"] / rep["total_generated"]) if rep["total_generated"] else 0.0

            results[sched][load] = {
                "deadline_miss_rate": overall_miss,
                "mean_latency": mean_lat if mean_lat is not None else 0.0,
                "p95_latency": p95 if p95 is not None else 0.0,
                "emergency_met_rate": emer_met,
                "admission_rate": adm_rate,
                "total_generated": rep.get("total_generated", 0),
                "total_admitted": rep.get("total_admitted", 0),
                "total_rejected": rep.get("total_rejected", 0),
                "total_dropped": rep.get("total_dropped", 0),
            }
    return results


def style_rc():
    plt.rcParams.update({
        "font.family": "Times New Roman",
        "figure.dpi": 300,
        "axes.grid": True,
        "grid.alpha": 0.25,
    })


def get_styles() -> Dict[str, Tuple[str, str]]:
    # Returns mapping: scheduler -> (color, marker)
    return {
        "FIFO": ("#1f77b4", "o"),
        "EMERGENCY_FIRST": ("#d62728", "s"),
        "STATIC_PRIORITY": ("#2ca02c", "^"),
        "SLA-DWP-Fog": ("#9467bd", "D"),
    }


def plot_metric(results, loads, metric_key: str, ylabel: str, fname: str, yscale: str | None = None):
    style_rc()
    fig, ax = plt.subplots(figsize=(6, 4))
    styles = get_styles()
    for sched, data in results.items():
        if sched not in styles:
            continue
        color, marker = styles[sched]
        yvals = [data[l].get(metric_key, 0.0) for l in loads]
        ax.plot(loads, yvals, marker=marker, color=color, linewidth=1.8, markersize=5, label=sched)
    ax.set_xlabel("Average requests per step")
    ax.set_ylabel(ylabel)
    if yscale:
        ax.set_yscale(yscale)
    ax.legend(frameon=False)
    fig.tight_layout()
    out = PLOTS_DIR / fname
    fig.savefig(out)
    plt.close(fig)


def save_json(results):
    out_json = PLOTS_DIR / "comparison_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def main():
    # Lighter start to show admission near 1.0 at low load
    loads = [2, 4, 6, 8, 10, 15, 20, 30, 40, 60, 80, 100]
    schedulers = ["FIFO", "EMERGENCY_FIRST", "STATIC_PRIORITY", "SLA-DWP-Fog"]
    results = run_grid(loads, schedulers)

    # Transpose for plotting convenience: {scheduler -> {load -> metrics}} is fine
    save_json(results)

    # Figures
    plot_metric(results, loads, "deadline_miss_rate", "Deadline Miss Rate", "fig1_deadline_miss.png")
    plot_metric(results, loads, "mean_latency", "Mean Latency (s)", "fig2_mean_latency.png")
    plot_metric(results, loads, "p95_latency", "P95 Latency (s)", "fig3_p95_latency.png")
    plot_metric(results, loads, "emergency_met_rate", "Emergency SLA Met Rate", "fig4_emergency_sla.png")
    plot_metric(results, loads, "admission_rate", "Admission Rate", "fig5_admission_rate.png")

    print(f"Saved figures and results to {PLOTS_DIR}")


if __name__ == "__main__":
    main()
