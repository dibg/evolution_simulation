"""Creatures and flowers: movement, vision cone, stamina, energy and behaviour.

Pure logic (math + random only) so the whole simulation runs headless.
"""
import math
import random

from genome import Genome, random_genome

TWO_PI = 2.0 * math.pi

# Movement tuning constants (not exposed as sliders).
CRUISE_FACTOR = 0.55     # fraction of top speed used while not sprinting
WALK_FACTOR = 0.35       # fraction of top speed when sprinting but exhausted
STAMINA_REGEN = 0.8      # stamina-seconds recovered per real second when not sprinting
SPRINT_METAB_MULT = 2.2  # energy drain multiplier while actively sprinting
TURN_RATE = 5.5          # radians/second a creature can rotate its heading
EAT_PAD = 5.0            # extra reach when eating / catching


def wrap_pi(a):
    return math.atan2(math.sin(a), math.cos(a))


def angle_to(src, dst):
    return math.atan2(dst.y - src.y, dst.x - src.x)


class Flower:
    __slots__ = ("x", "y", "radius", "alive", "variant")

    def __init__(self, x, y):
        self.x = x
        self.y = y
        # A per-flower seed (0..1) so the renderer can vary tint / size / petal
        # phase — keeps a field of flowers from looking like identical dots.
        self.variant = random.random()
        self.radius = 4 + int(self.variant * 2)   # 4..5 px
        self.alive = True


class Creature:
    species = "creature"
    quota_attr = "prey_food_quota"
    radius = 6

    def __init__(self, x, y, genome, s, generation=0):
        self.x = x
        self.y = y
        self.genome = genome
        self.heading = random.uniform(0.0, TWO_PI)
        self.age = 0.0
        self.energy = s.start_energy
        self.stamina = genome.stamina           # current sprint reserve (seconds)
        self.alive = True
        self.food_count = 0                      # progress toward breeding quota
        self.breed_cooldown = 0.0
        self.generation = generation
        self.sprinting = False
        self.state = "wander"
        self._wander_timer = random.uniform(0.0, 1.2)

    # --- helpers -----------------------------------------------------------
    def is_ready(self, s):
        """Fertile: ate its quota, mature, off cooldown and has spare energy."""
        quota = getattr(s, self.quota_attr)
        return (self.food_count >= quota
                and self.age >= s.maturity_age
                and self.breed_cooldown <= 0.0
                and self.energy > s.breed_cost * 1.2)

    def steer(self, target_angle, dt):
        diff = wrap_pi(target_angle - self.heading)
        max_turn = TURN_RATE * dt
        if diff > max_turn:
            diff = max_turn
        elif diff < -max_turn:
            diff = -max_turn
        self.heading = wrap_pi(self.heading + diff)

    def wander(self, dt):
        self._wander_timer -= dt
        if self._wander_timer <= 0.0:
            self.heading = wrap_pi(self.heading + random.uniform(-0.9, 0.9))
            self._wander_timer = random.uniform(0.5, 1.6)

    def _move(self, dt, world):
        speed = self.genome.speed
        if self.sprinting and self.stamina > 0.0:
            v = speed
            self.stamina = max(0.0, self.stamina - dt)
        elif self.sprinting:                 # sprinting but exhausted
            v = speed * WALK_FACTOR
        else:                                # cruising / wandering -> recover
            v = speed * CRUISE_FACTOR
            self.stamina = min(self.genome.stamina, self.stamina + STAMINA_REGEN * dt)

        self.x += math.cos(self.heading) * v * dt
        self.y += math.sin(self.heading) * v * dt

        # Bounce off the world edges.
        w, h = world.bounds
        m = self.radius
        if self.x < m:
            self.x = m
            self.heading = wrap_pi(math.pi - self.heading)
        elif self.x > w - m:
            self.x = w - m
            self.heading = wrap_pi(math.pi - self.heading)
        if self.y < m:
            self.y = m
            self.heading = wrap_pi(-self.heading)
        elif self.y > h - m:
            self.y = h - m
            self.heading = wrap_pi(-self.heading)

    def _separate(self, grid):
        """Gentle positional push so same-species creatures don't perfectly
        overlap — purely cosmetic (run after steering, so it never changes who
        flees/chases whom), but it makes a crowd read as many bodies, not a blob.
        """
        r = self.radius
        for o in grid.query(self.x, self.y, r * 2):
            if o is self or not o.alive:
                continue
            dx = self.x - o.x
            dy = self.y - o.y
            mind = r + o.radius
            d2 = dx * dx + dy * dy
            if d2 >= mind * mind:
                continue
            if d2 > 1e-9:
                d = math.sqrt(d2)
                push = (mind - d) * 0.5
                self.x += dx / d * push
                self.y += dy / d * push
            else:                                  # exactly coincident — jitter apart
                self.x += random.uniform(-1.0, 1.0)
                self.y += random.uniform(-1.0, 1.0)

    def _clamp(self, world):
        w, h = world.bounds
        r = self.radius
        if self.x < r:
            self.x = r
        elif self.x > w - r:
            self.x = w - r
        if self.y < r:
            self.y = r
        elif self.y > h - r:
            self.y = h - r

    def _metabolize(self, dt, s):
        gene_cost = s.metabolism * (0.4 * (self.genome.speed / 150.0)
                                    + 0.2 * (self.genome.stamina / 10.0))
        drain = s.metabolism + gene_cost
        if self.sprinting and self.stamina > 0.0:
            drain *= SPRINT_METAB_MULT
        self.energy -= drain * dt
        self.age += dt
        if self.breed_cooldown > 0.0:
            self.breed_cooldown -= dt
        if self.energy <= 0.0 or self.age >= s.lifespan:
            self.alive = False


class Prey(Creature):
    species = "prey"
    quota_attr = "prey_food_quota"
    radius = 6

    def update(self, world, dt):
        s = world.s
        # See a predator in the vision cone, OR sense one very close from any
        # direction (panic radius) — stops rear-blind-spot ambushes.
        predator = world.nearest_seen(self, world.predator_grid)
        if predator is None and s.panic_radius > 0:
            predator = world.nearest(self, world.predator_grid, s.panic_radius)
        if predator is not None:
            # Flee directly away from the threat.
            self.state = "flee"
            self.sprinting = True
            self.steer(math.atan2(self.y - predator.y, self.x - predator.x), dt)
        elif self.is_ready(s):
            self.sprinting = False
            mate = world.nearest_seen(self, world.prey_grid,
                                      lambda o: o is not self and o.alive and o.is_ready(s))
            if mate is not None:
                self.state = "seek_mate"
                self.steer(angle_to(self, mate), dt)
            else:
                self.state = "wander"
                self.wander(dt)
        else:
            self.sprinting = False
            flower = world.nearest_seen(self, world.flower_grid, lambda f: f.alive)
            if flower is not None:
                self.state = "seek_food"
                self.steer(angle_to(self, flower), dt)
            else:
                self.state = "wander"
                self.wander(dt)

        self._move(dt, world)
        self._separate(world.prey_grid)
        self._clamp(world)
        self._metabolize(dt, s)

        if not self.alive:                         # starved or died of old age
            world.events.append(("death", self.x, self.y, "prey"))
            return

        # Eat a flower we are touching.
        reach = self.radius + 4 + EAT_PAD
        flower = world.nearest(self, world.flower_grid, reach, lambda f: f.alive)
        if flower is not None:
            flower.alive = False
            self.energy = min(s.max_energy, self.energy + s.flower_energy)
            self.food_count += 1
            world.events.append(("eat", flower.x, flower.y, "prey"))


class Predator(Creature):
    species = "predator"
    quota_attr = "pred_food_quota"
    radius = 8

    def update(self, world, dt):
        s = world.s
        prey = world.nearest_seen(self, world.prey_grid, lambda o: o.alive)
        if prey is not None:
            self.state = "chase"
            self.sprinting = True
            self.steer(angle_to(self, prey), dt)
        elif self.is_ready(s):
            self.sprinting = False
            mate = world.nearest_seen(self, world.predator_grid,
                                      lambda o: o is not self and o.alive and o.is_ready(s))
            if mate is not None:
                self.state = "seek_mate"
                self.steer(angle_to(self, mate), dt)
            else:
                self.state = "wander"
                self.wander(dt)
        else:
            self.sprinting = False
            self.state = "wander"
            self.wander(dt)

        self._move(dt, world)
        self._separate(world.predator_grid)
        self._clamp(world)
        self._metabolize(dt, s)

        if not self.alive:                         # starved or died of old age
            world.events.append(("death", self.x, self.y, "predator"))
            return

        # Catch and eat a prey we are touching.
        reach = self.radius + 6 + EAT_PAD
        victim = world.nearest(self, world.prey_grid, reach, lambda o: o.alive)
        if victim is not None:
            victim.alive = False
            world.events.append(("kill", victim.x, victim.y, "prey"))
            self.energy = min(s.max_energy, self.energy + s.pred_eat_energy)
            self.food_count += 1


def make_creature(species, x, y, s, genome=None, generation=0):
    if genome is None:
        genome = random_genome(s, species)
    cls = Predator if species == "predator" else Prey
    return cls(x, y, genome, s, generation)
