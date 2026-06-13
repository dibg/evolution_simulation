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
WIN_W, WIN_H = 1280, 800
PANEL_W = 300
SIM_W, SIM_H = WIN_W - PANEL_W, WIN_H
FPS = 60

# --- colours ---------------------------------------------------------------
SIM_BG = (18, 20, 28)
GRID = (26, 29, 39)
FLOWER = (236, 120, 192)
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

SPEED_DISP = (40.0, 200.0)  # range used to map speed gene -> brightness


def _lerp_color(base, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return tuple(int(c + (255 - c) * 0.6 * t) for c in base)


class UIState:
    def __init__(self):
        self.paused = False
        self.tool = "inspect"        # inspect | prey | predator | flower
        self.show_vision = False
        self.show_panel = True       # is the right-hand settings panel open?
        self.fullscreen = False
        self.selected = None
        self.status = "ready"


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Predator–Prey Evolution")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusansmono,monospace", 14)
        self.small = pygame.font.SysFont("dejavusansmono,monospace", 13)
        self.big = pygame.font.SysFont("dejavusansmono,monospace", 17, bold=True)

        self.state = UIState()
        self.sim_w = SIM_W                       # current sim-area width (grows when panel hidden)
        self.s = load_settings()
        self.world = World(self.s, (self.sim_w, SIM_H))
        self.world.reset()
        self.sim_surf = pygame.Surface((WIN_W, SIM_H))   # full width; panel is drawn over the right strip

        buttons, toolbar_h = self._build_toolbar()
        self.panel = ui.Panel(pygame.Rect(SIM_W, 0, PANEL_W, WIN_H),
                              self.s, buttons, toolbar_h)
        # Floating panel toggle — anchored to the top-right corner, always drawn
        # on top, so it stays clickable whether the panel is open or hidden.
        self.toggle_btn = ui.Button(
            lambda: "hide ▸" if self.state.show_panel else "◂ settings",
            self.toggle_panel)
        self.toggle_btn.rect = pygame.Rect(WIN_W - 100, 8, 92, 24)

    # --- toolbar -----------------------------------------------------------
    def _build_toolbar(self):
        st = self.state
        specs_rows = [
            [("⏸ Pause/Play", self.toggle_pause, lambda: self.state.paused),
             ("↺ Reset", self.reset, None)],
            [("✖ Clear", self.clear, None),
             ("Vision cones", self.toggle_vision, lambda: self.state.show_vision)],
            [("⛶ Fullscreen (F11)", self.toggle_fullscreen, lambda: self.state.fullscreen)],
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
        x0 = SIM_W + ui.PAD
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

    def set_tool(self, tool):
        self.state.tool = tool

    def toggle_panel(self):
        self.state.show_panel = not self.state.show_panel
        # When the panel is hidden the simulation uses the full window width.
        self.sim_w = SIM_W if self.state.show_panel else WIN_W
        self.world.bounds = (self.sim_w, SIM_H)

    def toggle_fullscreen(self):
        self.state.fullscreen = not self.state.fullscreen
        # SCALED keeps the logical 1280x800 surface (and remaps the mouse), so the
        # whole layout/click logic is unchanged — SDL just scales it to the screen.
        if self.state.fullscreen:
            self.screen = pygame.display.set_mode(
                (WIN_W, WIN_H), pygame.SCALED | pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((WIN_W, WIN_H))

    def reset(self):
        self.world = World(self.s, (self.sim_w, SIM_H))
        self.world.reset()
        self.state.selected = None
        self.state.status = "reset"

    def clear(self):
        self.world.clear()
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

    def handle_event(self, event):
        mouse = pygame.mouse.get_pos()
        # The floating toggle is always interactive and takes priority.
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                and self.toggle_btn.rect.collidepoint(event.pos):
            self.toggle_btn.callback()
            return
        if self.state.show_panel and self.panel.handle_event(event, mouse):
            return
        if event.type == pygame.QUIT:
            self.running = False
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
                self.s.sim_speed = min(8.0, round(self.s.sim_speed + 0.25, 2))
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.s.sim_speed = max(0.0, round(self.s.sim_speed - 0.25, 2))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if mx < self.sim_w:
                tool = self.state.tool
                if tool == "inspect":
                    self.state.selected = self._pick_creature(mx, my)
                else:
                    self.world.spawn(tool, float(mx), float(my))

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
            remaining -= step
            guard += 1
        sel = self.state.selected
        if sel is not None and not sel.alive:
            self.state.selected = None

    # --- rendering ---------------------------------------------------------
    def _draw_vision(self, surf, c):
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
            shade = pygame.Surface((WIN_W, SIM_H), pygame.SRCALPHA)
            pygame.draw.polygon(shade, (*col, 26), pts)
            surf.blit(shade, (0, 0))
        except ValueError:
            pass

    def _draw_creature(self, surf, c, base):
        t = (c.genome.speed - SPEED_DISP[0]) / (SPEED_DISP[1] - SPEED_DISP[0])
        col = _lerp_color(base, t)
        r = c.radius
        cx, cy = int(c.x), int(c.y)
        if c.is_ready(self.s):
            pygame.draw.circle(surf, READY_RING, (cx, cy), r + 4, 2)
        pygame.draw.circle(surf, col, (cx, cy), r)
        # heading
        hx = c.x + math.cos(c.heading) * (r + 5)
        hy = c.y + math.sin(c.heading) * (r + 5)
        pygame.draw.line(surf, (245, 245, 245), (cx, cy), (hx, hy), 2)
        if c is self.state.selected:
            pygame.draw.circle(surf, SELECT, (cx, cy), r + 6, 2)

    def render(self):
        s = self.sim_surf
        s.fill(SIM_BG)
        # subtle grid across the full simulation width
        for gx in range(0, self.sim_w, 80):
            pygame.draw.line(s, GRID, (gx, 0), (gx, SIM_H))
        for gy in range(0, SIM_H, 80):
            pygame.draw.line(s, GRID, (0, gy), (self.sim_w, gy))

        for f in self.world.flowers:
            pygame.draw.circle(s, FLOWER, (int(f.x), int(f.y)), f.radius)
            pygame.draw.circle(s, FLOWER_CORE, (int(f.x), int(f.y)), 2)

        if self.state.show_vision:
            for c in self.world.prey:
                self._draw_vision(s, c)
            for c in self.world.predators:
                self._draw_vision(s, c)
        elif self.state.selected is not None and self.state.selected.species != "flower":
            self._draw_vision(s, self.state.selected)

        for c in self.world.prey:
            self._draw_creature(s, c, PREY_BASE)
        for c in self.world.predators:
            self._draw_creature(s, c, PRED_BASE)

        self.screen.blit(s, (0, 0))
        self._draw_hud()
        self._draw_inspector()
        if self.state.show_panel:
            self.panel.draw(self.screen, self.font, self.small)
            self.screen.blit(self.small.render("CONTROLS", True, ui.HEADER),
                             (SIM_W + ui.PAD, 14))
        self.toggle_btn.draw(self.screen, self.small)   # always on top
        pygame.display.flip()

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
        hint = "Space pause · 1-4 tools · click to spawn/inspect · V vision · P panel · F11 fullscreen · R reset · +/- speed"
        hs = self.small.render(hint, True, MUTED)
        bg = pygame.Surface((hs.get_width() + 16, hs.get_height() + 8), pygame.SRCALPHA)
        bg.fill((*HUD_BG, 190))
        self.screen.blit(bg, (8, WIN_H - hs.get_height() - 14))
        self.screen.blit(hs, (16, WIN_H - hs.get_height() - 10))

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
        rows = [
            (self.font, f"{c.species.upper()}  gen {c.generation}", col),
            (self.small, f"age {c.age:4.0f}/{self.s.lifespan:.0f}s", MUTED),
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

    # --- main loop ---------------------------------------------------------
    def run(self):
        self.running = True
        smoke = os.environ.get("SIM_SMOKE_FRAMES")
        max_frames = int(smoke) if smoke and smoke.isdigit() else None
        frames = 0
        while self.running:
            real_dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(real_dt)
            self.render()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                self.running = False
        pygame.quit()


def run_gui():
    App().run()
    return 0
