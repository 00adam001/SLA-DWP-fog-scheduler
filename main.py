# main.py
import argparse
import json
from pathlib import Path
from typing import Optional

from config import SimulationConfig
from simulation import Simulation


def run_and_maybe_export(config: SimulationConfig, out_path: Optional[Path], plot_path: Optional[Path]):
    sim = Simulation(config)
    results = sim.run()

    # Optionally save JSON
    if out_path is not None:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    # Optionally plot (requires matplotlib)
    if plot_path is not None:
        try:
            import matplotlib.pyplot as plt

            fig, axs = plt.subplots(2, 1, figsize=(8, 8))

            # Queue lengths over time
            avg_q = results.get("avg_queue_lengths") or []
            max_q = results.get("max_queue_lengths") or []
            if not avg_q and "avg_queue_length" in results and results["avg_queue_length"] is not None:
                # In case only aggregated stats are present, skip timeseries
                axs[0].text(0.5, 0.5, "No per-step queue time series available", ha='center')
            else:
                t = list(range(len(avg_q)))
                axs[0].plot(t, avg_q, label="avg_queue_length")
                axs[0].plot(t, max_q, label="max_queue_length")
                axs[0].set_title("Queue lengths over time")
                axs[0].set_xlabel("Time step")
                axs[0].set_ylabel("Requests in queue")
                axs[0].legend()

            # Latency histogram
            lats = results.get("latencies") or []
            if lats:
                axs[1].hist(lats, bins=20)
                axs[1].set_title("Latency histogram (s)")
                axs[1].set_xlabel("Latency (s)")
                axs[1].set_ylabel("Count")
            else:
                axs[1].text(0.5, 0.5, "No latency samples", ha='center')

            plt.tight_layout()
            plt.savefig(plot_path)
            plt.close(fig)
        except Exception as e:
            print(f"Unable to generate plot: {e}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fog-sim and optionally export metrics")
    parser.add_argument("--sim-time", type=float, default=None, help="total simulation time in seconds")
    parser.add_argument("--time-step-ms", type=int, default=None, help="time step in milliseconds (overrides --time-step)")
    parser.add_argument("--time-step", type=float, default=None, help="time step in seconds")
    parser.add_argument("--avg-requests", type=float, default=None, help="avg requests per step")
    parser.add_argument("--max-requests", type=int, default=None, help="max requests per step")
    parser.add_argument("--fog-cpu", type=float, default=None, help="fog cpu capacity (units per second)")
    parser.add_argument("--fog-link", type=float, default=None, help="fog link capacity (MB per second)")
    parser.add_argument("--fog-queue", type=int, default=None, help="per-node max queue length (None = unbounded)")
    parser.add_argument("--out", type=Path, default=None, help="Path to write JSON metrics")
    parser.add_argument("--plot", type=Path, default=None, help="Path to write PNG plot")
    args = parser.parse_args()

    # Start from default config and apply overrides
    cfg = SimulationConfig()
    if args.sim_time is not None:
        cfg.sim_time = args.sim_time
    if args.time_step_ms is not None:
        cfg.time_step_ms = args.time_step_ms
    if args.time_step is not None:
        cfg.time_step = args.time_step
    if args.avg_requests is not None:
        cfg.avg_requests_per_step = args.avg_requests
    if args.max_requests is not None:
        cfg.max_requests_per_step = args.max_requests
    if args.fog_cpu is not None:
        cfg.fog_cpu_capacity = args.fog_cpu
    if args.fog_link is not None:
        cfg.fog_link_capacity = args.fog_link
    if args.fog_queue is not None:
        cfg.fog_max_queue_length = args.fog_queue

    results = run_and_maybe_export(cfg, args.out, args.plot)

    print("=== Simulation Summary ===")
    for key, value in results.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
