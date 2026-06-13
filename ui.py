"""Hand-rolled pygame widgets: sliders, buttons and the scrolling control panel.

No third-party UI dependency — just pygame primitives — so it runs anywhere
pygame-ce installs.
"""
import pygame

from settings import SLIDER_GROUPS

# --- palette ---------------------------------------------------------------
PANEL_BG = (28, 30, 40)
BORDER = (60, 64, 80)
TEXT = (210, 214, 224)
MUTED = (140, 146, 160)
VALUE = (130, 200, 255)
ACCENT = (70, 130, 200)
TRACK_BG = (50, 54, 68)
KNOB = (205, 214, 232)
BTN_BG = (44, 48, 62)
BTN_FG = (205, 210, 222)
BTN_FG_ON = (245, 248, 255)
HEADER = (150, 170, 210)

PAD = 10


def _clamp01(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


class Button:
    def __init__(self, label, callback, active_fn=None):
        self.label = label              # str or callable -> str
        self.callback = callback
        self.active_fn = active_fn
        self.rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surf, font):
        active = bool(self.active_fn()) if self.active_fn else False
        pygame.draw.rect(surf, ACCENT if active else BTN_BG, self.rect, border_radius=4)
        pygame.draw.rect(surf, BORDER, self.rect, 1, border_radius=4)
        text = self.label() if callable(self.label) else self.label
        ts = font.render(text, True, BTN_FG_ON if active else BTN_FG)
        surf.blit(ts, (self.rect.centerx - ts.get_width() // 2,
                       self.rect.centery - ts.get_height() // 2))

    def handle_down(self, pos):
        if self.rect.collidepoint(pos):
            self.callback()
            return True
        return False


class Slider:
    ROW_H = 36

    def __init__(self, key, label, lo, hi, step, is_int):
        self.key = key
        self.label = label
        self.lo = lo
        self.hi = hi
        self.step = step
        self.is_int = is_int
        self.track = pygame.Rect(0, 0, 0, 0)
        self.hitbox = pygame.Rect(0, 0, 0, 0)

    def draw(self, surf, font, s, x, y, w, visible):
        self.track = pygame.Rect(x, y + 22, w, 5)
        self.hitbox = pygame.Rect(x, y, w, self.ROW_H)
        if visible:
            val = getattr(s, self.key)
            surf.blit(font.render(self.label, True, TEXT), (x, y))
            vstr = str(int(round(val))) if self.is_int else f"{val:.2f}"
            vs = font.render(vstr, True, VALUE)
            surf.blit(vs, (x + w - vs.get_width(), y))
            pygame.draw.rect(surf, TRACK_BG, self.track, border_radius=3)
            t = _clamp01((val - self.lo) / (self.hi - self.lo)) if self.hi > self.lo else 0.0
            if t > 0:
                pygame.draw.rect(surf, ACCENT,
                                 pygame.Rect(self.track.x, self.track.y,
                                             int(self.track.w * t), self.track.h),
                                 border_radius=3)
            kx = self.track.x + int(self.track.w * t)
            pygame.draw.circle(surf, KNOB, (kx, self.track.centery), 7)
            pygame.draw.circle(surf, BORDER, (kx, self.track.centery), 7, 1)
        return self.ROW_H

    def set_from_x(self, s, mx):
        if self.track.w <= 0:
            return
        t = _clamp01((mx - self.track.x) / self.track.w)
        v = self.lo + t * (self.hi - self.lo)
        if self.step:
            v = round(v / self.step) * self.step
        if self.is_int:
            v = int(round(v))
        v = max(self.lo, min(self.hi, v))
        setattr(s, self.key, v)


class Panel:
    """The right-hand control panel: a fixed toolbar of buttons on top, then a
    scrollable list of sliders grouped under headers."""

    def __init__(self, rect, settings, buttons, toolbar_h):
        self.rect = rect
        self.s = settings
        self.buttons = buttons
        self.toolbar_h = toolbar_h
        self.scroll = 0.0
        self.drag = None
        # flat list of ('h', text) / ('s', Slider)
        self.items = []
        self.sliders = []
        for gname, defs in SLIDER_GROUPS:
            self.items.append(("h", gname))
            for (key, label, lo, hi, step, is_int) in defs:
                sl = Slider(key, label, lo, hi, step, is_int)
                self.items.append(("s", sl))
                self.sliders.append(sl)
        self.content_h = PAD * 2 + sum(24 if k == "h" else Slider.ROW_H for k, _ in self.items)

    @property
    def area(self):
        top = self.rect.y + self.toolbar_h
        return pygame.Rect(self.rect.x, top, self.rect.w, self.rect.bottom - top)

    def _max_scroll(self):
        return max(0.0, self.content_h - self.area.height)

    # --- events ------------------------------------------------------------
    def handle_event(self, event, mouse_pos):
        """Return True if the panel consumed the event."""
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos):
                self.scroll = max(0.0, min(self._max_scroll(), self.scroll - event.y * 32))
                return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                return False
            for b in self.buttons:
                if b.handle_down(event.pos):
                    return True
            if self.area.collidepoint(event.pos):
                for sl in self.sliders:
                    if sl.hitbox.collidepoint(event.pos):
                        self.drag = sl
                        sl.set_from_x(self.s, event.pos[0])
                        return True
            return True  # consume any click inside the panel
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.drag is not None:
                self.drag = None
                return True
            return False
        if event.type == pygame.MOUSEMOTION and self.drag is not None:
            self.drag.set_from_x(self.s, event.pos[0])
            return True
        return False

    # --- draw --------------------------------------------------------------
    def draw(self, surf, font, small):
        pygame.draw.rect(surf, PANEL_BG, self.rect)
        pygame.draw.line(surf, BORDER, (self.rect.x, self.rect.y),
                         (self.rect.x, self.rect.bottom))
        for b in self.buttons:
            b.draw(surf, small)

        area = self.area
        self.scroll = max(0.0, min(self._max_scroll(), self.scroll))
        prev_clip = surf.get_clip()
        surf.set_clip(area)
        x = self.rect.x + PAD
        w = self.rect.w - 2 * PAD
        yy = area.y + PAD - int(self.scroll)
        for kind, item in self.items:
            if kind == "h":
                if area.y - 24 < yy < area.bottom:
                    surf.blit(small.render(item.upper(), True, HEADER), (x, yy + 6))
                    pygame.draw.line(surf, BORDER, (x, yy + 22), (x + w, yy + 22))
                yy += 24
            else:
                visible = area.y - Slider.ROW_H < yy < area.bottom
                yy += item.draw(surf, small, self.s, x, yy, w, visible)
        surf.set_clip(prev_clip)

        # scrollbar
        ms = self._max_scroll()
        if ms > 0:
            frac = area.height / self.content_h
            bar_h = max(24, int(area.height * frac))
            bar_y = area.y + int((area.height - bar_h) * (self.scroll / ms))
            pygame.draw.rect(surf, BORDER,
                             pygame.Rect(self.rect.right - 5, bar_y, 3, bar_h),
                             border_radius=2)
