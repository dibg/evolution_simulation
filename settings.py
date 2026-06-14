"""All tunable parameters of the simulation.

`Settings` is a flat dataclass of every parameter. `SLIDER_GROUPS` describes
which of them are exposed as live sliders in the control panel (and their
ranges), so adding a new knob is a one-line change here.
"""
import json
import os
import sys
from dataclasses import dataclass, asdict, fields

if getattr(sys, "frozen", False):
    # Packed into a single executable (PyInstaller): save an editable config.json
    # next to the binary, and fall back to the copy bundled inside it.
    _BASE = os.path.dirname(sys.executable)
    _BUNDLED = os.path.join(getattr(sys, "_MEIPASS", _BASE), "config.json")
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _BUNDLED = os.path.join(_BASE, "config.json")

CONFIG_PATH = os.path.join(_BASE, "config.json")   # where Save cfg writes


@dataclass
class Settings:
    # --- Display ---
    ui_scale: float = 0.0           # UI/world zoom (0 = auto-detect the desktop scale)

    # --- Time / simulation ---
    sim_speed: float = 1.0          # time multiplier (0 = frozen)
    lifespan: float = 300.0         # max age in seconds (default 5 minutes)

    # --- Flowers (prey food) ---
    flower_interval: float = 45.0   # seconds between natural flower growth
    flower_batch: int = 10          # flowers added each growth tick
    max_flowers: int = 240          # cap on flowers in the world
    initial_flowers: int = 80       # flowers present at reset
    flower_energy: float = 35.0     # energy a prey gains per flower

    # --- Vision (field-of-view cone) ---
    vision_range: float = 140.0     # how far a creature can see (pixels)
    vision_angle: float = 220.0     # full cone angle in degrees
    panic_radius: float = 55.0      # prey sense a predator this close from ANY direction

    # --- Genetics (per-species spawn ranges; both evolve via mutation) ---
    mutation_rate: float = 0.12     # mutation strength (0 = clones, 1 = wild)
    prey_speed_min: float = 75.0    # prey are bred fast (to escape)
    prey_speed_max: float = 125.0
    prey_stamina_min: float = 5.0
    prey_stamina_max: float = 11.0
    pred_speed_min: float = 65.0    # predators are a bit slower...
    pred_speed_max: float = 105.0
    pred_stamina_min: float = 9.0   # ...but more enduring (wear prey down)
    pred_stamina_max: float = 17.0

    # --- Energy / metabolism (starvation) ---
    metabolism: float = 1.2         # base energy drained per second
    max_energy: float = 100.0
    start_energy: float = 70.0      # energy a newborn / spawned creature starts with
    pred_eat_energy: float = 60.0   # energy a predator gains per prey eaten
    breed_cost: float = 30.0        # energy each parent spends to breed
    breed_cooldown: float = 6.0     # seconds before a parent can breed again

    # --- Breeding ---
    prey_food_quota: int = 4        # flowers a prey must eat to become fertile
    pred_food_quota: int = 3        # prey a predator must eat to become fertile
    maturity_age: float = 6.0       # seconds before a creature can breed

    # --- Populations ---
    initial_prey: int = 50          # (applied on reset)
    initial_predators: int = 6
    max_prey: int = 240
    max_predators: int = 70


# Curated sliders shown in the panel, grouped under headers.
# Each entry: (key, label, lo, hi, step, is_int)
SLIDER_GROUPS = [
    ("Display", [
        ("ui_scale", "UI scale (0=auto)", 0.0, 3.0, 0.25, False),
    ]),
    ("Time / simulation", [
        ("sim_speed", "Sim speed", 0.0, 8.0, 0.25, False),
        ("lifespan", "Lifespan (s)", 30, 900, 10, True),
    ]),
    ("Flowers", [
        ("flower_interval", "Grow every (s)", 5, 180, 5, True),
        ("flower_batch", "Grow batch", 1, 40, 1, True),
        ("max_flowers", "Max flowers", 20, 600, 10, True),
        ("flower_energy", "Flower energy", 5, 80, 1, True),
    ]),
    ("Vision", [
        ("vision_range", "Vision range", 30, 400, 5, True),
        ("vision_angle", "Vision angle", 30, 360, 5, True),
        ("panic_radius", "Prey panic radius", 0, 200, 5, True),
    ]),
    ("Genetics — global", [
        ("mutation_rate", "Mutation rate", 0.0, 1.0, 0.01, False),
    ]),
    ("Genetics — prey (spawn)", [
        ("prey_speed_min", "Prey speed min", 10, 250, 5, True),
        ("prey_speed_max", "Prey speed max", 20, 300, 5, True),
        ("prey_stamina_min", "Prey stamina min", 1, 30, 1, True),
        ("prey_stamina_max", "Prey stamina max", 2, 45, 1, True),
    ]),
    ("Genetics — predator (spawn)", [
        ("pred_speed_min", "Pred speed min", 10, 250, 5, True),
        ("pred_speed_max", "Pred speed max", 20, 300, 5, True),
        ("pred_stamina_min", "Pred stamina min", 1, 30, 1, True),
        ("pred_stamina_max", "Pred stamina max", 2, 45, 1, True),
    ]),
    ("Energy / metabolism", [
        ("metabolism", "Metabolism", 0.2, 6.0, 0.1, False),
        ("start_energy", "Start energy", 10, 100, 5, True),
        ("pred_eat_energy", "Energy per prey", 10, 100, 5, True),
        ("breed_cost", "Breed cost", 0, 80, 5, True),
        ("breed_cooldown", "Breed cooldown (s)", 0, 30, 1, True),
    ]),
    ("Breeding", [
        ("prey_food_quota", "Prey: flowers to breed", 1, 12, 1, True),
        ("pred_food_quota", "Pred: prey to breed", 1, 12, 1, True),
        ("maturity_age", "Maturity age (s)", 0, 40, 1, True),
    ]),
    ("Populations (reset to apply)", [
        ("initial_prey", "Initial prey", 0, 300, 5, True),
        ("initial_predators", "Initial predators", 0, 100, 1, True),
        ("initial_flowers", "Initial flowers", 0, 400, 10, True),
        ("max_prey", "Max prey", 10, 500, 10, True),
        ("max_predators", "Max predators", 5, 300, 5, True),
    ]),
]


def load_settings(path=None):
    """Start from defaults, overlay any values found in config.json (preferring
    an editable one next to the app, else the bundled copy)."""
    s = Settings()
    if path is None:
        path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else _BUNDLED
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            valid = {f.name: f.type for f in fields(Settings)}
            for k, v in data.items():
                if k in valid:
                    setattr(s, k, int(v) if valid[k] is int else float(v) if valid[k] is float else v)
        except (OSError, ValueError):
            pass
    return s


def reset_settings(s):
    """Reset every field of `s` to its built-in default value, in place.
    Mutates the existing object so all references to it stay valid."""
    d = Settings()
    for f in fields(Settings):
        setattr(s, f.name, getattr(d, f.name))
    return s


def save_settings(s, path=CONFIG_PATH):
    try:
        with open(path, "w") as f:
            json.dump(asdict(s), f, indent=2)
        return True
    except OSError:
        return False
