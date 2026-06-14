# Predator–Prey Evolution

A live ecosystem simulation in Python + pygame. Flowers grow, **prey** eat
flowers, **predators** hunt prey, and creatures **breed in pairs** — passing on
genes for **speed** and **stamina** that mutate and evolve over generations. You
mostly watch, but you can spawn creatures and tune every parameter while it runs.

![species](https://img.shields.io/badge/prey-green-brightgreen) ![species](https://img.shields.io/badge/predators-red-red) ![species](https://img.shields.io/badge/flowers-pink-ff69b4)

## Run it

```bash
./run.sh
```

The first run creates a local `.venv` and installs `pygame-ce` automatically.
(Manual equivalent: `python3 -m venv .venv && ./.venv/bin/pip install pygame-ce && ./.venv/bin/python main.py`.)

Headless sanity check (no window, prints population/gene stats):

```bash
./.venv/bin/python main.py --selftest 9000
```

## One clickable file (no Python needed)

To get a **single self-contained executable** that bundles Python, pygame and SDL
— so it runs with nothing installed — build it once:

```bash
./build.sh        # -> dist/predator-prey-evolution  (one file, ~17 MB)
```

Then just run / double-click `dist/predator-prey-evolution`. No venv, no pip, no
Python required on the machine that runs it. (If your file manager asks, choose
"Run"; first time you may need to tick *Allow executing file as program* in its
Properties.)

Portability note: a binary built on one machine runs on Linux with the **same or
newer glibc**. For an older distro like **Linux Mint**, run `./build.sh` *on that
machine* to produce a native single file there (it only needs `python3-venv` +
internet for the one-time build; `setup.sh` installs those).

## Move it to another Linux machine (e.g. Linux Mint)

The project is plain Python — only the local `.venv` is machine-specific, so it
is never copied. Two easy ways:

**Copy a clean tarball:**

```bash
./pack.sh                       # makes ../predator-prey-evolution.tar.gz
# …copy that file to the new machine, then there:
tar -xzf predator-prey-evolution.tar.gz
cd game
./setup.sh                      # one-time: installs deps (asks for sudo), builds .venv
./run.sh
```

**Or just copy the folder** (without `.venv`) and run `./run.sh` — it rebuilds the
virtualenv and installs dependencies on first launch.

On a fresh Mint/Ubuntu install you only need Python's venv/pip packages, which
`setup.sh` installs for you (or manually: `sudo apt install python3-venv python3-pip`).
`pygame-ce` itself ships prebuilt wheels, so there's nothing to compile.
`setup.sh` can also add a **Predator–Prey Evolution** entry to your applications menu.

## How the world works

- **Flowers** sprout naturally in batches every *Grow every (s)* seconds, up to a cap.
- **Prey** (green) roam, eat flowers, and flee predators they see — or sense via
  their **panic radius** (so they can't be ambushed from directly behind).
- **Predators** (red) chase the nearest prey inside their **vision cone** and eat
  it on contact.
- **Energy / starvation:** every creature burns energy continuously (faster when
  sprinting and for higher-stat genomes). Eating refills it; at 0 energy it dies.
  Creatures also die of **old age** (lifespan) and prey die by being **eaten**.
- **Breeding (two parents):** a prey that has eaten *4 flowers* and a predator
  that has eaten *3 prey* become **fertile** (yellow ring). When two fertile
  adults of the same species meet, a baby is born whose **speed & stamina genes
  are a blend of both parents, plus mutation**. Both parents then pay an energy
  cost and enter a cooldown.
- **Evolution:** prey start fast (to escape) and predators start enduring (to
  wear prey down), but mutation + natural selection push the genes over time.
  Watch the **avg speed / stamina** in the HUD drift across generations.

**Reading the world at a glance**

- Each creature is drawn as a little arrow pointing where it's headed; **brighter
  = faster genes**, **dimmer = low on energy** (a starving creature visibly fades).
- A pulsing **yellow ring** marks a fertile adult ready to breed.
- Moments flash so you don't miss them: a pink ring when prey nibbles a flower, a
  **red pop** when a predator makes a kill, a bright ring for a **birth**, and a
  grey puff when something dies of hunger or old age.
- The bottom-right **charts** (toggle with `G`) plot population and average speed
  over the last few minutes — this is where you actually *see* selection happen.

The default parameters produce a real predator–prey cycle: predators boom and
crash the prey, prey recover, and after a few minutes prey usually "win" the
arms race and predators fade. Keep them going by spawning more predators, raising
their speed genes, increasing flower supply, or raising the mutation rate — all
live in the panel.

## Controls

**Mouse**
- Pick a **spawn tool** (Prey / Predator / Flower) in the panel, then **left-click
  in the world** to place one. A translucent **ghost** previews what you'll drop.
- **Drag** with a spawn tool held to *paint* a trail of creatures or flowers.
- **Right-click** anywhere to delete the creature (or flower) under the cursor.
- **Inspect** tool: click a creature to see its genes, energy, stamina, current
  behaviour and breeding progress in the bottom-left readout.
- Drag any **slider** to change a parameter live. Scroll the panel with the wheel.

**Keyboard**
- `Space` pause/resume · `R` reset · `C` clear all
- `1` inspect · `2` prey · `3` predator · `4` flower
- `V` toggle vision cones · `G` toggle the live charts · `P` / `Tab` hide/show the
  settings panel · `F11` fullscreen · `+ / -` simulation speed · `Ctrl + / Ctrl -`
  UI scale · `Esc` exits fullscreen / quits · `Q` quit

The window is freely **resizable** — drag any edge and the world, panel and charts
re-flow to fit (the simulation area simply gets bigger). **F11** switches to
fullscreen at your **native desktop resolution** (not an upscaled 1280×800), and
`Esc` drops back to the window.

**HiDPI / display scaling:** the app auto-detects your desktop's UI scale (so it
won't render tiny on a fractionally-scaled, e.g. 1.5×, display). If the guess is
off, set it explicitly with the **UI scale** slider (top of the panel; `0` = auto),
**Ctrl + / Ctrl -**, or the `PPE_SCALE` environment variable — then **Save cfg** to
keep it. Everything is drawn on a logical canvas and scaled to the window, so the
whole UI *and* the world grow together.

The **hide ▸** button in the top-right corner collapses the settings panel so the
simulation fills the whole window; while hidden it becomes **◂ settings** and stays
in the corner so you can bring the panel back.

## Parameters

All knobs live in the panel (and in `config.json`, loaded at startup). Highlights:
lifespan, flower growth rate / batch / cap, vision range & angle, prey panic
radius, mutation rate, per-species speed & stamina spawn ranges, metabolism,
energy per meal, breed cost & cooldown, breeding food quotas, and starting /
maximum populations. **Save cfg** writes the current values back to `config.json`;
**Load cfg** reloads them. Population sliders (and gene spawn ranges) take effect
on the next **Reset**. **Reset settings to defaults** restores every parameter to
its built-in value (independent of `config.json`).

## Files

| file | role |
|------|------|
| `main.py` | entry point (`--selftest` runs headless) |
| `gui.py` | window, rendering, input, main loop |
| `ui.py` | sliders / buttons / scrolling control panel |
| `simulation.py` | the `World`: stepping, breeding, flower growth, stats |
| `entities.py` | prey, predators, flowers — movement & behaviour |
| `genome.py` | genes, crossover, mutation |
| `spatial.py` | spatial-hash grid for fast neighbour lookups |
| `settings.py` | all parameters + slider definitions |
| `config.json` | saved default parameters |
