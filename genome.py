"""Genetics: the heritable traits, crossover and mutation.

Traits: speed, stamina (movement), plus size and vision (body/senses). Each
species has its own spawn ranges for speed/stamina, while size & vision seed
from shared ranges; all of them evolve within wider hard limits. No external
dependencies so this module is usable in headless --selftest runs.
"""
import random
from dataclasses import dataclass

# Hard evolutionary bounds. The per-species *spawn* ranges in Settings only seed
# the initial population; mutation may push genes anywhere inside these wider
# limits so traits can genuinely evolve beyond the starting distribution.
SPEED_HARD = (5.0, 400.0)
STAMINA_HARD = (0.5, 45.0)
SIZE_HARD = (0.55, 1.9)        # body-radius multiplier
VISION_HARD = (0.5, 1.9)       # vision-range multiplier

# Fixed reference spans for mutation magnitude (so mutation step is stable even
# as the user narrows/widens the spawn ranges).
SPEED_MUT_SPAN = 80.0
STAMINA_MUT_SPAN = 8.0
SIZE_MUT_SPAN = 0.6
VISION_MUT_SPAN = 0.6


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


@dataclass
class Genome:
    speed: float      # max movement speed in pixels/second
    stamina: float    # sprint capacity in seconds
    size: float = 1.0    # body-radius multiplier (bigger = stronger reach, costlier)
    vision: float = 1.0  # vision-range multiplier (farther sight, costlier)

    def copy(self):
        return Genome(self.speed, self.stamina, self.size, self.vision)


def random_genome(s, species):
    """A fresh genome drawn uniformly from the species' spawn ranges."""
    if species == "predator":
        speed = random.uniform(s.pred_speed_min, s.pred_speed_max)
        stamina = random.uniform(s.pred_stamina_min, s.pred_stamina_max)
    else:
        speed = random.uniform(s.prey_speed_min, s.prey_speed_max)
        stamina = random.uniform(s.prey_stamina_min, s.prey_stamina_max)
    return Genome(
        speed=speed,
        stamina=stamina,
        size=random.uniform(s.size_min, s.size_max),
        vision=random.uniform(s.vision_min, s.vision_max),
    )


def crossover(a, b):
    """Blend two parents. Each gene is an independent random interpolation
    between the parents' values (so siblings differ)."""
    def blend(x, y):
        t = random.random()
        return x * t + y * (1.0 - t)
    return Genome(
        speed=blend(a.speed, b.speed),
        stamina=blend(a.stamina, b.stamina),
        size=blend(a.size, b.size),
        vision=blend(a.vision, b.vision),
    )


def mutate(g, s):
    """Apply Gaussian mutation scaled by the global mutation_rate, in place."""
    rate = s.mutation_rate
    if rate > 0:
        g.speed += random.gauss(0.0, rate * SPEED_MUT_SPAN * 0.5)
        g.stamina += random.gauss(0.0, rate * STAMINA_MUT_SPAN * 0.5)
        g.size += random.gauss(0.0, rate * SIZE_MUT_SPAN * 0.5)
        g.vision += random.gauss(0.0, rate * VISION_MUT_SPAN * 0.5)
    g.speed = clamp(g.speed, *SPEED_HARD)
    g.stamina = clamp(g.stamina, *STAMINA_HARD)
    g.size = clamp(g.size, *SIZE_HARD)
    g.vision = clamp(g.vision, *VISION_HARD)
    return g
