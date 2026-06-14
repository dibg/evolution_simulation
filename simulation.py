"""The World: owns all entities, advances them each step, handles flower
growth, two-parent breeding, deaths and statistics. No rendering here.
"""
import math
import random
from collections import deque

from entities import Prey, Predator, Flower, make_creature
from genome import crossover, mutate
from spatial import SpatialGrid

# How many per-second samples the rolling history keeps (for the live charts).
HISTORY_LEN = 240


class World:
    def __init__(self, s, bounds):
        self.s = s
        self.bounds = bounds            # (width, height) of the simulation area
        self.prey = []
        self.predators = []
        self.flowers = []
        self.sim_time = 0.0
        self.flower_timer = 0.0
        self.generation = 0
        self.births = 0
        self.deaths = 0
        self.half_angle = math.radians(s.vision_angle) * 0.5
        # grids are rebuilt every step
        self.prey_grid = SpatialGrid(40)
        self.predator_grid = SpatialGrid(40)
        self.flower_grid = SpatialGrid(40)
        # Transient one-step event log (eat / kill / birth / death) consumed by
        # the renderer to spawn effects; cleared at the start of every step().
        self.events = []
        # Rolling time-series for the live charts: one sample per sim-second.
        self.history = deque(maxlen=HISTORY_LEN)
        self._hist_timer = 0.0

    # --- setup -------------------------------------------------------------
    def _rand_pos(self):
        w, h = self.bounds
        return random.uniform(20, w - 20), random.uniform(20, h - 20)

    def reset(self):
        self.prey.clear()
        self.predators.clear()
        self.flowers.clear()
        self.sim_time = 0.0
        self.flower_timer = 0.0
        self.generation = 0
        self.births = 0
        self.deaths = 0
        self.events = []
        self.history.clear()
        self._hist_timer = 0.0
        s = self.s
        for _ in range(int(s.initial_flowers)):
            x, y = self._rand_pos()
            self.flowers.append(Flower(x, y))
        for _ in range(int(s.initial_prey)):
            x, y = self._rand_pos()
            self.prey.append(make_creature("prey", x, y, s))
        for _ in range(int(s.initial_predators)):
            x, y = self._rand_pos()
            self.predators.append(make_creature("predator", x, y, s))

    def clear(self):
        self.prey.clear()
        self.predators.clear()
        self.flowers.clear()

    # --- spawning (used by the UI) ----------------------------------------
    def spawn(self, species, x, y):
        s = self.s
        if species == "flower":
            self.flowers.append(Flower(x, y))
            return
        c = make_creature(species, x, y, s)
        (self.predators if species == "predator" else self.prey).append(c)

    # --- neighbour queries -------------------------------------------------
    def nearest_seen(self, observer, grid, predicate=None):
        """Nearest entity inside the observer's vision cone."""
        s = self.s
        vr = s.vision_range
        vr2 = vr * vr
        half = self.half_angle
        full_circle = half >= math.pi
        best = None
        best_d = vr2 + 1.0
        ox, oy, oh = observer.x, observer.y, observer.heading
        for o in grid.query(ox, oy, vr):
            if o is observer:
                continue
            if predicate is not None and not predicate(o):
                continue
            dx = o.x - ox
            dy = o.y - oy
            d2 = dx * dx + dy * dy
            if d2 > vr2 or d2 >= best_d:
                continue
            if not full_circle:
                rel = math.atan2(dy, dx) - oh
                if abs(math.atan2(math.sin(rel), math.cos(rel))) > half:
                    continue
            best_d = d2
            best = o
        return best

    def nearest(self, observer, grid, radius, predicate=None):
        """Nearest entity within a plain radius (ignores the vision cone)."""
        r2 = radius * radius
        best = None
        best_d = r2 + 1.0
        ox, oy = observer.x, observer.y
        for o in grid.query(ox, oy, radius):
            if o is observer:
                continue
            if predicate is not None and not predicate(o):
                continue
            dx = o.x - ox
            dy = o.y - oy
            d2 = dx * dx + dy * dy
            if d2 <= r2 and d2 < best_d:
                best_d = d2
                best = o
        return best

    # --- the step ----------------------------------------------------------
    def _build_grids(self):
        cell = max(40.0, self.s.vision_range)
        self.prey_grid = SpatialGrid(cell)
        self.predator_grid = SpatialGrid(cell)
        self.flower_grid = SpatialGrid(cell)
        for c in self.prey:
            if c.alive:
                self.prey_grid.insert(c, c.x, c.y)
        for c in self.predators:
            if c.alive:
                self.predator_grid.insert(c, c.x, c.y)
        for f in self.flowers:
            if f.alive:
                self.flower_grid.insert(f, f.x, f.y)

    def _breed(self, group, grid, max_pop, species):
        """Pair up fertile, touching adults and produce offspring."""
        s = self.s
        if len(group) >= max_pop:
            return []
        ready = [c for c in group if c.alive and c.is_ready(s)]
        used = set()
        newborns = []
        for a in ready:
            if id(a) in used or len(group) + len(newborns) >= max_pop:
                continue
            reach = a.radius * 2 + 8
            mate = self.nearest(
                a, grid, reach,
                lambda o: o is not a and o.alive and id(o) not in used and o.is_ready(s))
            if mate is None:
                continue
            child_genome = mutate(crossover(a.genome, mate.genome), s)
            gen = max(a.generation, mate.generation) + 1
            cx = (a.x + mate.x) * 0.5 + random.uniform(-6, 6)
            cy = (a.y + mate.y) * 0.5 + random.uniform(-6, 6)
            child = make_creature(species, cx, cy, s, child_genome, gen)
            for p in (a, mate):
                p.breed_cooldown = s.breed_cooldown
                p.food_count = 0
                p.energy -= s.breed_cost
            used.add(id(a))
            used.add(id(mate))
            newborns.append(child)
            self.events.append(("birth", child.x, child.y, species))
            self.generation = max(self.generation, gen)
        return newborns

    def step(self, dt):
        s = self.s
        self.half_angle = math.radians(s.vision_angle) * 0.5
        self.sim_time += dt
        self.events = []          # fresh per step; the renderer drains it after
        self._build_grids()

        for c in self.prey:
            if c.alive:
                c.update(self, dt)
        for c in self.predators:
            if c.alive:
                c.update(self, dt)

        newborns_prey = self._breed(self.prey, self.prey_grid, int(s.max_prey), "prey")
        newborns_pred = self._breed(self.predators, self.predator_grid, int(s.max_predators), "predator")

        before = len(self.prey) + len(self.predators)
        self.prey = [c for c in self.prey if c.alive] + newborns_prey
        self.predators = [c for c in self.predators if c.alive] + newborns_pred
        self.flowers = [f for f in self.flowers if f.alive]
        self.births += len(newborns_prey) + len(newborns_pred)
        # deaths = (alive before + born) - alive after ... track simply
        after_alive = len(self.prey) + len(self.predators)
        born = len(newborns_prey) + len(newborns_pred)
        self.deaths += max(0, before + born - after_alive)

        # Natural flower growth.
        self.flower_timer += dt
        if s.flower_interval > 0:
            while self.flower_timer >= s.flower_interval and len(self.flowers) < s.max_flowers:
                self.flower_timer -= s.flower_interval
                grow = min(int(s.flower_batch), int(s.max_flowers) - len(self.flowers))
                for _ in range(grow):
                    x, y = self._rand_pos()
                    self.flowers.append(Flower(x, y))
            if self.flower_timer > s.flower_interval:
                self.flower_timer = self.flower_timer % s.flower_interval

        # Sample the rolling history once per sim-second for the live charts.
        self._hist_timer += dt
        if self._hist_timer >= 1.0:
            self._hist_timer -= 1.0
            st = self.stats()
            self.history.append((
                st["prey"], st["predators"], st["flowers"],
                st["prey_speed"], st["pred_speed"],
            ))

    # --- statistics --------------------------------------------------------
    def stats(self):
        def avg(group, attr):
            if not group:
                return 0.0
            return sum(getattr(c.genome, attr) for c in group) / len(group)
        return {
            "prey": len(self.prey),
            "predators": len(self.predators),
            "flowers": len(self.flowers),
            "generation": self.generation,
            "births": self.births,
            "deaths": self.deaths,
            "prey_speed": avg(self.prey, "speed"),
            "prey_stamina": avg(self.prey, "stamina"),
            "pred_speed": avg(self.predators, "speed"),
            "pred_stamina": avg(self.predators, "stamina"),
            "time": self.sim_time,
        }
