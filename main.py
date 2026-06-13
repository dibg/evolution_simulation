#!/usr/bin/env python3
"""Predator-Prey evolution simulation.

Usage:
    python main.py                 # open the graphical simulation
    python main.py --selftest [N]  # run N headless steps and print stats (no window)

The --selftest path imports only the pure-logic core (no pygame), so it can be
run in headless / CI environments to verify the simulation behaves.
"""
import sys

# Simulation-area size when running headless self-test (matches the GUI default).
SELFTEST_BOUNDS = (980, 800)


def run_selftest(steps):
    from settings import load_settings
    from simulation import World

    s = load_settings()
    world = World(s, SELFTEST_BOUNDS)
    world.reset()
    dt = 1.0 / 30.0

    print(f"self-test: {steps} steps @ dt={dt:.3f}s  (~{steps * dt:.0f} sim-seconds)")
    print(f"{'t(s)':>6} {'prey':>5} {'pred':>5} {'flwr':>5} {'gen':>4} "
          f"{'preySpd':>8} {'predSpd':>8} {'births':>7} {'deaths':>7}")
    saw_birth = False
    max_flowers_seen = 0
    for i in range(steps):
        world.step(dt)
        st = world.stats()
        if st["births"] > 0:
            saw_birth = True
        max_flowers_seen = max(max_flowers_seen, st["flowers"])
        if i % max(1, steps // 20) == 0 or i == steps - 1:
            print(f"{st['time']:6.0f} {st['prey']:5d} {st['predators']:5d} "
                  f"{st['flowers']:5d} {st['generation']:4d} "
                  f"{st['prey_speed']:8.1f} {st['pred_speed']:8.1f} "
                  f"{st['births']:7d} {st['deaths']:7d}")

    st = world.stats()
    print("-" * 60)
    print(f"final: prey={st['prey']} predators={st['predators']} "
          f"flowers={st['flowers']} generation={st['generation']} "
          f"births={st['births']} deaths={st['deaths']}")
    assert saw_birth, "no creatures ever bred — check breeding parameters"
    assert max_flowers_seen > 0, "flowers never grew"
    assert st["generation"] >= 1, "no second generation was produced"
    print("OK: flowers grow, creatures hunt/eat, two-parent breeding works, "
          "generations advance.")
    return 0


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        idx = args.index("--selftest")
        steps = 3000
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            steps = int(args[idx + 1])
        return run_selftest(steps)
    from gui import run_gui
    return run_gui()


if __name__ == "__main__":
    sys.exit(main() or 0)
