"""Graphical front-end: window, rendering, input handling and the main loop.

Imports pygame, so this module is only loaded for the real GUI (the headless
--selftest path in main.py never imports it).
"""
import math
import os

import pygame

import ui
from settings import load_settings, save_settings, reset_settings
from simulation import World

# --- window layout ---------------------------------------------------------
DEFAULT_W, DEFAULT_H = 1280, 800   # initial windowed size
MIN_W, MIN_H = 720, 540            # smallest size the layout still works at
PANEL_W = 300                      # the settings panel is a fixed-width strip
FPS = 60

# --- colours ---------------------------------------------------------------
SIM_BG = (18, 20, 28)
GRID = (26, 29, 39)
FLOWER = (236, 120, 192)
FLOWER_ALT = (250, 174, 150)   # second petal tint; flowers lerp between the two
FLOWER_CORE = (255, 232, 130)
PREY_BASE = (60, 200, 110)
PRED_BASE = (228, 84, 72)
READY_RING = (250, 220, 90)
SELECT = (255, 255, 255)
HUD_BG = (12, 14, 20)
TEXT = (212, 216, 226)
MUTED = (146, 152, 166)
PREY_TXT = (110, 220, 150)
PRED_TXT = (240, 130, 120)
BAR_BG = (44, 48, 60)
ENERGY_COL = (120, 200, 120)
STAM_COL = (110, 170, 240)
GRAPH_BG = (10, 12, 18)

SPEED_DISP = (40.0, 200.0)  # range used to map speed gene -> brightness

# Visual spec for each transient world event. (ttl, start-r, end-r, base-alpha,
# fill?). Colour is chosen per event (species/flower) when the effect is spawned.
FX_SPEC = {
    "eat":   (0.45,  4, 15, 170, False),   # prey nibbles a flower
    "kill":  (0.55,  5, 30, 190, True),    # predator catches prey — red pop
    "birth": (0.70,  2, 22, 200, False),   # newborn appears
    "death": (0.55,  4, 18, 150, False),   # starved / old age — grey puff
}


def _lerp_color(base, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return tuple(int(c + (255 - c) * 0.6 * t) for c in base)


def _mix(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _clampf(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _detect_os_scale():
    """Best-effort guess at the desktop's UI scaling so the app doesn't render
    tiny on a HiDPI / fractionally-scaled display (SDL otherwise ignores it).

    Honoured in order: an explicit PPE_SCALE override, the common toolkit env
    hints, then X resources (Xft.dpi / 96). Falls back to 1.0 — the user can
    always override with the 'UI scale' slider or Ctrl +/-.
    """
    env = os.environ.get("PPE_SCALE")
    if env:
        try:
            return _clampf(float(env), 0.5, 3.0)
        except ValueError:
            pass
    for var in ("GDK_DPI_SCALE", "QT_SCALE_FACTOR", "GDK_SCALE"):
        v = os.environ.get(var)
        if v:
            try:
                return _clampf(float(v), 0.5, 3.0)
            except ValueError:
                pass
    try:
        import subprocess
        out = subprocess.run(["xrdb", "-query"], capture_output=True,
                             text=True, timeout=1).stdout
        for line in out.splitlines():
            if line.startswith("Xft.dpi:"):
                dpi = float(line.split(":", 1)[1].strip())
                if dpi > 0:
                    return _clampf(round(dpi / 96.0 * 4) / 4, 0.5, 3.0)
    except Exception:
        pass
    return 1.0


class UIState:
    def __init__(self):
        self.paused = False
        self.tool = "inspect"        # inspect | prey | predator | flower
        self.show_vision = False
        self.show_panel = True       # is the right-hand settings panel open?
        self.show_graphs = True      # the live population / gene charts overlay
        self.fullscreen = False
        self.selected = None
        self.status = "ready"


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Predator–Prey Evolution")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusansmono,monospace", 14)
        self.small = pygame.font.SysFont("dejavusansmono,monospace", 13)
        self.big = pygame.font.SysFont("dejavusansmono,monospace", 17, bold=True)

        self.state = UIState()
        self.s = load_settings()
        # Display scaling. Everything is laid out / drawn at a *logical* size
        # (win_w x win_h) onto a canvas, which is then scaled up to the real
        # window (phys_w x phys_h). scale = physical / logical pixels.
        self._auto_scale = _detect_os_scale()
        self.scale = self.s.ui_scale if self.s.ui_scale > 0 else self._auto_scale
        self.phys_w, self.phys_h = self._initial_window_size()
        self._windowed_size = (self.phys_w, self.phys_h)   # restored when leaving fullscreen
        self.display = pygame.display.set_mode((self.phys_w, self.phys_h), pygame.RESIZABLE)

        self.world = World(self.s, (1, 1))       # bounds set by _relayout()
        self.effects = []                        # live event animations
        self._painting = False                   # drag-to-paint with a spawn tool
        self._paint_last = (0.0, 0.0)
        self.mouse = (0, 0)
        self.panel = None

        # Floating panel toggle — anchored to the top-right corner, always drawn
        # on top, so it stays clickable whether the panel is open or hidden.
        self.toggle_btn = ui.Button(
            lambda: "hide ▸" if self.state.show_panel else "◂ settings",
            self.toggle_panel)
        self._relayout()                         # sizes canvas, surfaces, panel, toggle
        self.world.reset()                       # now that bounds are correct

    # --- display scaling ---------------------------------------------------
    def _initial_window_size(self):
        """A physical window size that fits the desktop, scaled up so the logical
        layout (1280x800-ish) stays comfortable at the detected UI scale."""
        try:
            sizes = pygame.display.get_desktop_sizes()
            dw, dh = sizes[0] if sizes else (1920, 1080)
        except Exception:
            info = pygame.display.Info()
            dw, dh = info.current_w or 1920, info.current_h or 1080
        w = min(round(DEFAULT_W * self.scale), dw - 20)
        h = min(round(DEFAULT_H * self.scale), dh - 80)
        w = max(round(MIN_W * self.scale), int(w))
        h = max(round(MIN_H * self.scale), int(h))
        return int(w), int(h)

    def _map(self, p):
        """Physical mouse pos -> logical canvas coords."""
        return (p[0] * self.win_w / self.phys_w, p[1] * self.win_h / self.phys_h)

    def _xlate(self, event):
        """Return a copy of a mouse event with its position mapped to logical
        coords, so all the layout/click logic can stay in logical space."""
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                           pygame.MOUSEMOTION) and hasattr(event, "pos"):
            d = dict(event.dict)
            d["pos"] = self._map(event.pos)
            if "rel" in d:
                d["rel"] = (event.rel[0] * self.win_w / self.phys_w,
                            event.rel[1] * self.win_h / self.phys_h)
            return pygame.event.Event(event.type, d)
        return event

    def _apply_scale(self, scale):
        self.scale = _clampf(scale, 0.5, 3.0)
        self._relayout()

    def _bump_scale(self, delta):
        new = _clampf(round((self.scale + delta) / 0.25) * 0.25, 0.5, 3.0)
        self.s.ui_scale = new            # becomes an explicit, saveable choice
        self._apply_scale(new)
        self.state.status = f"UI scale {new:.2f}"

    def _sync_scale(self):
        """Pick up scale changes from the settings slider (0 = auto). Skipped
        while a slider is being dragged so we don't rebuild the panel mid-drag."""
        if self.panel is not None and self.panel.drag is not None:
            return
        desired = self.s.ui_scale if self.s.ui_scale > 0 else self._auto_scale
        desired = _clampf(desired, 0.5, 3.0)
        if abs(desired - self.scale) > 1e-3:
            self._apply_scale(desired)

    # --- layout ------------------------------------------------------------
    def _relayout(self):
        """Recompute everything that depends on size/scale. Called at start and
        whenever the window is resized, the scale changes, or the panel toggles.

        Layout happens in *logical* pixels (win_w x win_h = physical / scale);
        the canvas is drawn there and scaled up to the physical window."""
        self.win_w = max(1, round(self.phys_w / self.scale))
        self.win_h = max(1, round(self.phys_h / self.scale))
        self.sim_h = self.win_h
        self.sim_w = (self.win_w - PANEL_W) if self.state.show_panel else self.win_w
        self.world.bounds = (self.sim_w, self.sim_h)
        # the logical canvas everything is drawn onto, plus two reused alpha
        # layers (vision cones go *under* the creatures, effects go *over*).
        self.screen = pygame.Surface((self.win_w, self.win_h))
        self.sim_surf = pygame.Surface((self.win_w, self.win_h))
        self._vision_overlay = pygame.Surface((self.win_w, self.win_h), pygame.SRCALPHA)
        self._fx_overlay = pygame.Surface((self.win_w, self.win_h), pygame.SRCALPHA)
        # the panel/toolbar geometry is anchored to the right edge → rebuild it,
        # preserving the user's current scroll position.
        prev_scroll = self.panel.scroll if self.panel is not None else 0.0
        buttons, toolbar_h = self._build_toolbar()
        self.panel = ui.Panel(pygame.Rect(self.win_w - PANEL_W, 0, PANEL_W, self.win_h),
                              self.s, buttons, toolbar_h)
        self.panel.scroll = prev_scroll
        self.toggle_btn.rect = pygame.Rect(self.win_w - 100, 8, 92, 24)

    def _resize(self, w, h):
        w = max(round(MIN_W * self.scale), w)
        h = max(round(MIN_H * self.scale), h)
        if (w, h) == (self.phys_w, self.phys_h):
            return
        self.phys_w, self.phys_h = w, h
        self.display = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        self._relayout()

    # --- toolbar -----------------------------------------------------------
    def _build_toolbar(self):
        st = self.state
        specs_rows = [
            [("⏸ Pause/Play", self.toggle_pause, lambda: self.state.paused),
             ("↺ Reset", self.reset, None)],
            [("✖ Clear", self.clear, None),
             ("⛶ Fullscreen", self.toggle_fullscreen, lambda: self.state.fullscreen)],
            [("Vision cones", self.toggle_vision, lambda: self.state.show_vision),
             ("Charts", self.toggle_graphs, lambda: self.state.show_graphs)],
            None,  # label: Spawn tool
            [("Inspect", lambda: self.set_tool("inspect"), lambda: self.state.tool == "inspect"),
             ("Prey", lambda: self.set_tool("prey"), lambda: self.state.tool == "prey")],
            [("Predator", lambda: self.set_tool("predator"), lambda: self.state.tool == "predator"),
             ("Flower", lambda: self.set_tool("flower"), lambda: self.state.tool == "flower")],
            None,  # label: Config
            [("Save cfg", self.save_cfg, None),
             ("Load cfg", self.load_cfg, None)],
            [("⟲ Reset settings to defaults", self.reset_defaults, None)],
        ]
        buttons = []
        x0 = (self.win_w - PANEL_W) + ui.PAD
        w = PANEL_W - 2 * ui.PAD
        bw = (w - 8) // 2
        y = 38  # leave a top strip clear for the floating panel-toggle button
        for row in specs_rows:
            if row is None:
                y += 18
                continue
            for i, (label, cb, active) in enumerate(row):
                b = ui.Button(label, cb, active)
                if len(row) == 1:
                    b.rect = pygame.Rect(x0, y, w, 24)          # full-width row
                else:
                    b.rect = pygame.Rect(x0 + i * (bw + 8), y, bw, 24)
                buttons.append(b)
            y += 30
        toolbar_h = y + 6
        return buttons, toolbar_h

    # --- actions -----------------------------------------------------------
    def toggle_pause(self):
        self.state.paused = not self.state.paused

    def toggle_vision(self):
        self.state.show_vision = not self.state.show_vision

    def toggle_graphs(self):
        self.state.show_graphs = not self.state.show_graphs

    def set_tool(self, tool):
        self.state.tool = tool

    def toggle_panel(self):
        # When the panel is hidden the simulation uses the full window width.
        self.state.show_panel = not self.state.show_panel
        self._relayout()

    def toggle_fullscreen(self):
        want = not self.state.fullscreen
        try:
            if want:
                # Native fullscreen at the desktop resolution. Pass the desktop
                # size explicitly (the (0,0) "current mode" form is quirky on
                # some window managers / Wayland) so the world fills the screen.
                self._windowed_size = (self.phys_w, self.phys_h)
                try:
                    sizes = pygame.display.get_desktop_sizes()
                    dw, dh = sizes[0] if sizes else (0, 0)
                except Exception:
                    dw, dh = 0, 0
                self.display = pygame.display.set_mode((dw, dh), pygame.FULLSCREEN)
            else:
                self.display = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)
        except pygame.error as e:
            # Some window managers refuse a mode change — stay where we are
            # rather than taking the whole app down.
            self.state.status = f"fullscreen failed: {e}"
            self.display = pygame.display.set_mode(
                (self.phys_w, self.phys_h), pygame.RESIZABLE)
            self.state.fullscreen = False
            self.phys_w, self.phys_h = self.display.get_size()
            self._relayout()
            return
        self.state.fullscreen = want
        self.phys_w, self.phys_h = self.display.get_size()
        self._relayout()

    def reset(self):
        self.world = World(self.s, (self.sim_w, self.sim_h))
        self.world.reset()
        self.effects.clear()
        self.state.selected = None
        self.state.status = "reset"

    def clear(self):
        self.world.clear()
        self.effects.clear()
        self.state.selected = None
        self.state.status = "cleared"

    def reset_defaults(self):
        reset_settings(self.s)
        self.state.status = "settings reset to defaults (Reset to apply pop/gene ranges)"

    def save_cfg(self):
        self.state.status = "saved config.json" if save_settings(self.s) else "save failed"

    def load_cfg(self):
        self.s = load_settings()
        # rebind settings used by world/panel
        self.world.s = self.s
        self.panel.s = self.s
        self.state.status = "loaded config.json"

    # --- input -------------------------------------------------------------
    def _pick_creature(self, x, y):
        best, best_d = None, 18.0 ** 2
        for group in (self.world.predators, self.world.prey):
            for c in group:
                if not c.alive:
                    continue
                d = (c.x - x) ** 2 + (c.y - y) ** 2
                if d < best_d:
                    best_d, best = d, c
        return best

    def _delete_at(self, x, y):
        """Right-click removal: kill the creature under the cursor (a small grey
        puff marks the spot), else remove the nearest flower there."""
        c = self._pick_creature(x, y)
        if c is not None:
            c.alive = False
            self._add_effect("death", c.x, c.y, c.species)
            if c is self.state.selected:
                self.state.selected = None
            return
        best, best_d = None, 16.0 ** 2
        for f in self.world.flowers:
            if not f.alive:
                continue
            d = (f.x - x) ** 2 + (f.y - y) ** 2
            if d < best_d:
                best_d, best = d, f
        if best is not None:
            best.alive = False

    def handle_event(self, event):
        mouse = self._map(pygame.mouse.get_pos())
        self.mouse = mouse
        # The floating toggle is always interactive and takes priority.
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                and self.toggle_btn.rect.collidepoint(event.pos):
            self.toggle_btn.callback()
            return
        if self.state.show_panel and self.panel.handle_event(event, mouse):
            return
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            if not self.state.fullscreen:
                self._resize(event.w, event.h)
        elif event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_q:
                self.running = False
            elif k == pygame.K_ESCAPE:
                if self.state.fullscreen:     # Esc leaves fullscreen first
                    self.toggle_fullscreen()
                else:
                    self.running = False
            elif k in (pygame.K_F11, pygame.K_f):
                self.toggle_fullscreen()
            elif k == pygame.K_SPACE:
                self.toggle_pause()
            elif k == pygame.K_r:
                self.reset()
            elif k == pygame.K_c:
                self.clear()
            elif k == pygame.K_v:
                self.toggle_vision()
            elif k == pygame.K_g:
                self.toggle_graphs()
            elif k in (pygame.K_p, pygame.K_TAB):
                self.toggle_panel()
            elif k == pygame.K_1:
                self.set_tool("inspect")
            elif k == pygame.K_2:
                self.set_tool("prey")
            elif k == pygame.K_3:
                self.set_tool("predator")
            elif k == pygame.K_4:
                self.set_tool("flower")
            elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self._bump_scale(+0.25)      # Ctrl + : larger UI / world
                else:
                    self.s.sim_speed = min(8.0, round(self.s.sim_speed + 0.25, 2))
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self._bump_scale(-0.25)      # Ctrl - : smaller UI / world
                else:
                    self.s.sim_speed = max(0.0, round(self.s.sim_speed - 0.25, 2))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if mx < self.sim_w:
                tool = self.state.tool
                if tool == "inspect":
                    self.state.selected = self._pick_creature(mx, my)
                else:
                    self.world.spawn(tool, float(mx), float(my))
                    self._painting = True        # begin drag-to-paint
                    self._paint_last = (mx, my)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._painting = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            mx, my = event.pos
            if mx < self.sim_w:
                self._delete_at(float(mx), float(my))
        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            # Holding the left button with a spawn tool paints a trail of them.
            if self._painting and self.state.tool != "inspect" and mx < self.sim_w:
                gap = 18.0 if self.state.tool == "flower" else 26.0
                lx, ly = self._paint_last
                if (mx - lx) ** 2 + (my - ly) ** 2 >= gap * gap:
                    self.world.spawn(self.state.tool, float(mx), float(my))
                    self._paint_last = (mx, my)

    # --- effects -----------------------------------------------------------
    def _add_effect(self, etype, x, y, species):
        spec = FX_SPEC.get(etype)
        if spec is None:
            return
        ttl, r0, r1, alpha, fill = spec
        if etype == "eat":
            col = FLOWER
        elif etype == "kill":
            col = PRED_BASE
        elif etype == "birth":
            col = PRED_BASE if species == "predator" else PREY_BASE
        else:                                  # death
            col = MUTED
        # Cap concurrent effects so a high-speed burst can't pile up unbounded.
        if len(self.effects) < 240:
            self.effects.append([etype, x, y, 0.0, ttl, r0, r1, alpha, fill, col])

    def _drain_events(self):
        for ev in self.world.events:
            etype, x, y, species = ev
            self._add_effect(etype, x, y, species)

    def _tick_effects(self, real_dt):
        if not self.effects:
            return
        for e in self.effects:
            e[3] += real_dt
        self.effects = [e for e in self.effects if e[3] < e[4]]

    # --- simulation --------------------------------------------------------
    def update(self, real_dt):
        if self.state.paused or self.s.sim_speed <= 0:
            return
        remaining = real_dt * self.s.sim_speed
        max_step = 1.0 / 30.0
        guard = 0
        while remaining > 1e-6 and guard < 16:
            step = max_step if remaining > max_step else remaining
            self.world.step(step)
            self._drain_events()             # capture every sub-step's events
            remaining -= step
            guard += 1
        sel = self.state.selected
        if sel is not None and not sel.alive:
            self.state.selected = None

    # --- rendering ---------------------------------------------------------
    def _draw_vision(self, overlay, c):
        """Draw one creature's vision cone onto the shared (already-cleared)
        alpha overlay — no per-creature surface allocation."""
        half = self.world.half_angle
        vr = self.s.vision_range
        pts = [(c.x, c.y)]
        steps = 10
        start = c.heading - half
        for i in range(steps + 1):
            a = start + (2 * half) * (i / steps)
            pts.append((c.x + math.cos(a) * vr, c.y + math.sin(a) * vr))
        col = PRED_BASE if c.species == "predator" else PREY_BASE
        try:
            pygame.draw.polygon(overlay, (*col, 26), pts)
        except ValueError:
            pass

    def _body_points(self, x, y, heading, r, species):
        """An arrowhead/teardrop pointing along the heading (predators a touch
        sharper than prey), used for both real creatures and the cursor ghost."""
        nose = 1.8 if species == "predator" else 1.5
        spread = 2.45
        cos, sin = math.cos, math.sin
        return [
            (x + cos(heading) * r * nose, y + sin(heading) * r * nose),
            (x + cos(heading + spread) * r, y + sin(heading + spread) * r),
            (x + cos(heading - spread) * r, y + sin(heading - spread) * r),
        ]

    def _draw_creature(self, surf, c, base):
        r = c.radius
        cx, cy = int(c.x), int(c.y)
        # Hue brightness encodes the speed gene; darkness encodes low energy —
        # so a fast, well-fed creature is vivid and a starving one is dim.
        t = (c.genome.speed - SPEED_DISP[0]) / (SPEED_DISP[1] - SPEED_DISP[0])
        col = _lerp_color(base, t)
        e = c.energy / self.s.max_energy
        e = 0.0 if e < 0 else 1.0 if e > 1 else e
        shade = 0.4 + 0.6 * e
        col = (int(col[0] * shade), int(col[1] * shade), int(col[2] * shade))
        if c.is_ready(self.s):                       # fertile — gently pulsing ring
            pulse = 4 + int(2.0 * (0.5 + 0.5 * math.sin(self.world.sim_time * 6.0)))
            pygame.draw.circle(surf, READY_RING, (cx, cy), r + pulse, 2)
        # Body: a filled circle plus a forward-pointing nose polygon.
        pygame.draw.circle(surf, col, (cx, cy), r)
        pygame.draw.polygon(surf, col, self._body_points(c.x, c.y, c.heading, r, c.species))
        edge = _mix(col, (0, 0, 0), 0.35)
        pygame.draw.circle(surf, edge, (cx, cy), r, 1)
        if c is self.state.selected:
            pygame.draw.circle(surf, SELECT, (cx, cy), r + 6, 2)

    def _draw_flower(self, surf, f):
        col = _mix(FLOWER, FLOWER_ALT, f.variant)
        # a slow per-flower bloom pulse so a field of them shimmers slightly
        pulse = 0.5 + 0.5 * math.sin(self.world.sim_time * 1.6 + f.variant * 6.28)
        r = f.radius + int(pulse)
        fx, fy = int(f.x), int(f.y)
        pygame.draw.circle(surf, col, (fx, fy), r)
        pygame.draw.circle(surf, FLOWER_CORE, (fx, fy), 2)

    def render(self):
        s = self.sim_surf
        s.fill(SIM_BG)
        # subtle grid across the full simulation width
        for gx in range(0, self.sim_w, 80):
            pygame.draw.line(s, GRID, (gx, 0), (gx, self.sim_h))
        for gy in range(0, self.sim_h, 80):
            pygame.draw.line(s, GRID, (0, gy), (self.sim_w, gy))

        for f in self.world.flowers:
            self._draw_flower(s, f)

        # Vision cones: one shared, cleared-once alpha layer, blitted once.
        show_all = self.state.show_vision
        sel = self.state.selected
        show_sel = (not show_all and sel is not None and sel.species != "flower")
        if show_all or show_sel:
            self._vision_overlay.fill((0, 0, 0, 0))
            if show_all:
                for c in self.world.prey:
                    self._draw_vision(self._vision_overlay, c)
                for c in self.world.predators:
                    self._draw_vision(self._vision_overlay, c)
            else:
                self._draw_vision(self._vision_overlay, sel)
            s.blit(self._vision_overlay, (0, 0))

        for c in self.world.prey:
            self._draw_creature(s, c, PREY_BASE)
        for c in self.world.predators:
            self._draw_creature(s, c, PRED_BASE)

        # Event effects + cursor ghost go on the second shared alpha layer
        # (over the creatures), again blitted once.
        if self.effects or self._ghost_active():
            self._fx_overlay.fill((0, 0, 0, 0))
            self._draw_effects(self._fx_overlay)
            self._draw_ghost(self._fx_overlay)
            s.blit(self._fx_overlay, (0, 0))

        self.screen.blit(s, (0, 0))
        self._draw_hud()
        self._draw_inspector()
        if self.state.show_graphs:
            self._draw_graphs()
        if self.state.show_panel:
            self.panel.draw(self.screen, self.font, self.small)
            self.screen.blit(self.small.render("CONTROLS", True, ui.HEADER),
                             (self.win_w - PANEL_W + ui.PAD, 14))
        self.toggle_btn.draw(self.screen, self.small)   # always on top

        # Composite the logical canvas onto the real (physical) window. When
        # they match (scale == 1) it's a plain blit; otherwise scale it up and
        # blit (blit converts pixel formats, so this works even when the window
        # surface has a different bit depth than the canvas — e.g. a 24-bit
        # fullscreen surface on X11, which the dest-arg form of smoothscale
        # would reject).
        if (self.win_w, self.win_h) == (self.phys_w, self.phys_h):
            self.display.blit(self.screen, (0, 0))
        else:
            self.display.blit(
                pygame.transform.smoothscale(self.screen, (self.phys_w, self.phys_h)),
                (0, 0))
        pygame.display.flip()

    def _draw_effects(self, overlay):
        for etype, x, y, age, ttl, r0, r1, alpha, fill, col in self.effects:
            p = age / ttl if ttl > 0 else 1.0
            r = int(r0 + (r1 - r0) * p)
            if r < 1:
                continue
            a = int(alpha * (1.0 - p))
            if a <= 0:
                continue
            pos = (int(x), int(y))
            if fill:
                pygame.draw.circle(overlay, (*col, a), pos, r)
            else:
                pygame.draw.circle(overlay, (*col, a), pos, r, 2)

    def _ghost_active(self):
        mx, my = self.mouse
        return (self.state.tool != "inspect" and mx < self.sim_w and 0 <= my < self.sim_h)

    def _draw_ghost(self, overlay):
        """A translucent preview of what the active spawn tool will place."""
        if not self._ghost_active():
            return
        mx, my = self.mouse
        tool = self.state.tool
        if tool == "flower":
            pygame.draw.circle(overlay, (*FLOWER, 120), (mx, my), 5)
            pygame.draw.circle(overlay, (*FLOWER, 70), (mx, my), 10, 1)
            return
        base = PRED_BASE if tool == "predator" else PREY_BASE
        r = 8 if tool == "predator" else 6
        pygame.draw.circle(overlay, (*base, 110), (mx, my), r)
        pygame.draw.polygon(overlay, (*base, 110),
                            self._body_points(mx, my, 0.0, r, tool))
        pygame.draw.circle(overlay, (*base, 80), (mx, my), r + 4, 1)

    def _bar(self, x, y, w, frac, col):
        frac = 0.0 if frac < 0 else 1.0 if frac > 1 else frac
        pygame.draw.rect(self.screen, BAR_BG, (x, y, w, 7), border_radius=2)
        if frac > 0:
            pygame.draw.rect(self.screen, col, (x, y, int(w * frac), 7), border_radius=2)

    def _draw_hud(self):
        st = self.world.stats()
        t = int(st["time"])
        lines = [
            (self.big, f"Prey {st['prey']}   Predators {st['predators']}   Flowers {st['flowers']}", TEXT),
            (self.small, f"gen {st['generation']}   time {t // 60:02d}:{t % 60:02d}   "
                         f"births {st['births']}  deaths {st['deaths']}", MUTED),
            (self.small, f"prey  speed {st['prey_speed']:5.1f}  stamina {st['prey_stamina']:4.1f}", PREY_TXT),
            (self.small, f"pred  speed {st['pred_speed']:5.1f}  stamina {st['pred_stamina']:4.1f}", PRED_TXT),
            (self.small, f"speed x{self.s.sim_speed:.2f}   {self.clock.get_fps():4.0f} fps   "
                         f"tool: {self.state.tool}", MUTED),
        ]
        w = 360
        h = 12 + sum(f.get_height() + 3 for f, _, _ in lines)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((*HUD_BG, 200))
        self.screen.blit(overlay, (8, 8))
        y = 14
        for font, txt, col in lines:
            self.screen.blit(font.render(txt, True, col), (16, y))
            y += font.get_height() + 3
        if self.state.paused:
            ps = self.big.render("❚❚ PAUSED", True, (255, 210, 90))
            self.screen.blit(ps, (16, y))
        # controls hint
        hint = ("Space pause · 1-4 tools · click spawn/inspect (drag to paint) · "
                "right-click delete · V vision · G charts · P panel · F11 full · R reset · +/- speed")
        hs = self.small.render(hint, True, MUTED)
        bg = pygame.Surface((hs.get_width() + 16, hs.get_height() + 8), pygame.SRCALPHA)
        bg.fill((*HUD_BG, 190))
        self.screen.blit(bg, (8, self.win_h - hs.get_height() - 14))
        self.screen.blit(hs, (16, self.win_h - hs.get_height() - 10))

    def _draw_inspector(self):
        c = self.state.selected
        if c is None or not c.alive:
            return
        quota = getattr(self.s, c.quota_attr)
        w, h = 230, 132
        x, y = 8, 120
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        box.fill((*HUD_BG, 215))
        self.screen.blit(box, (x, y))
        pygame.draw.rect(self.screen, ui.BORDER, (x, y, w, h), 1)
        col = PRED_TXT if c.species == "predator" else PREY_TXT
        state_label = {
            "wander": "wandering", "flee": "fleeing!", "chase": "chasing",
            "seek_food": "seeking food", "seek_mate": "seeking mate",
        }.get(c.state, c.state)
        rows = [
            (self.font, f"{c.species.upper()}  gen {c.generation}", col),
            (self.small, f"age {c.age:4.0f}/{self.s.lifespan:.0f}s   {state_label}", MUTED),
            (self.small, f"speed gene   {c.genome.speed:6.1f}", TEXT),
            (self.small, f"stamina gene {c.genome.stamina:6.1f}", TEXT),
            (self.small, f"food {c.food_count}/{quota}  "
                         f"{'READY' if c.is_ready(self.s) else 'growing'}", TEXT),
        ]
        yy = y + 8
        for font, txt, cc in rows:
            self.screen.blit(font.render(txt, True, cc), (x + 10, yy))
            yy += font.get_height() + 2
        self.screen.blit(self.small.render("energy", True, MUTED), (x + 10, yy))
        self._bar(x + 70, yy + 3, w - 90, c.energy / self.s.max_energy, ENERGY_COL)
        yy += 16
        self.screen.blit(self.small.render("stamina", True, MUTED), (x + 10, yy))
        self._bar(x + 70, yy + 3, w - 90,
                  c.stamina / c.genome.stamina if c.genome.stamina else 0, STAM_COL)

    # --- live charts -------------------------------------------------------
    def _plot(self, surf, series, x, y, w, h, lo, hi, col):
        n = len(series)
        if n < 2 or hi <= lo:
            return
        span = hi - lo
        denom = n - 1
        pts = [(x + w * (i / denom),
                y + h - 1 - (h - 1) * ((v - lo) / span))
               for i, v in enumerate(series)]
        pygame.draw.lines(surf, col, False, pts, 1)

    def _draw_graphs(self):
        hist = self.world.history
        gw, gh = 300, 132
        gx = self.sim_w - gw - 12
        gy = self.sim_h - gh - 46
        box = pygame.Surface((gw, gh), pygame.SRCALPHA)
        box.fill((*GRAPH_BG, 205))
        self.screen.blit(box, (gx, gy))
        pygame.draw.rect(self.screen, ui.BORDER, (gx, gy, gw, gh), 1)

        pad = 8
        cw = gw - 2 * pad
        chart_h = 38
        if len(hist) < 2:
            self.screen.blit(self.small.render("charts: gathering data…", True, MUTED),
                             (gx + pad, gy + pad))
            return

        prey = [d[0] for d in hist]
        pred = [d[1] for d in hist]
        pspd = [d[3] for d in hist]
        xspd = [d[4] for d in hist]

        # --- population over time ---
        y0 = gy + pad + 14
        self.screen.blit(self.small.render(
            f"population   prey {prey[-1]}   pred {pred[-1]}", True, MUTED),
            (gx + pad, gy + pad - 1))
        pmax = max(max(prey), max(pred), 1)
        self._plot(self.screen, prey, gx + pad, y0, cw, chart_h, 0, pmax, PREY_TXT)
        self._plot(self.screen, pred, gx + pad, y0, cw, chart_h, 0, pmax, PRED_TXT)

        # --- average speed gene over time ---
        y1 = y0 + chart_h + 16
        self.screen.blit(self.small.render(
            f"avg speed   prey {pspd[-1]:.0f}   pred {xspd[-1]:.0f}", True, MUTED),
            (gx + pad, y1 - 15))
        vals = pspd + xspd
        lo, hi = min(vals), max(vals)
        if hi - lo < 1.0:                      # flat line — give it some headroom
            lo, hi = lo - 5, hi + 5
        else:
            pad_v = (hi - lo) * 0.1
            lo, hi = lo - pad_v, hi + pad_v
        self._plot(self.screen, pspd, gx + pad, y1, cw, chart_h, lo, hi, PREY_TXT)
        self._plot(self.screen, xspd, gx + pad, y1, cw, chart_h, lo, hi, PRED_TXT)

    # --- main loop ---------------------------------------------------------
    def run(self):
        self.running = True
        smoke = os.environ.get("SIM_SMOKE_FRAMES")
        max_frames = int(smoke) if smoke and smoke.isdigit() else None
        frames = 0
        while self.running:
            real_dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(self._xlate(event))
            self.mouse = self._map(pygame.mouse.get_pos())
            self._sync_scale()
            self.update(real_dt)
            self._tick_effects(real_dt)
            self.render()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                self.running = False
        pygame.quit()


def run_gui():
    App().run()
    return 0
