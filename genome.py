"""Genetics: the two heritable traits (speed, stamina), crossover and mutation.

Each species has its own spawn ranges (prey are bred to be fast, predators to be
enduring), but both evolve within the same wide hard limits. No external
dependencies so this module is usable in headless --selftest runs.
"""
import random
from dataclasses import dataclass

# Hard evolutionary bounds. The per-species *spawn* ranges in Settings only seed
# the initial population; mutation may push genes anywhere inside these wider
# limits so traits can genuinely evolve beyond the starting distribution.
SPEED_HARD = (5.0, 400.0)
STAMINA_HARD = (0.5, 45.0)

# Fixed reference spans for mutation magnitude (so mutation step is stable even
# as the user narrows/widens the spawn ranges).
SPEED_MUT_SPAN = 80.0
STAMINA_MUT_SPAN = 8.0


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


@dataclass
class Genome:
    speed: float      # max movement speed in pixels/second
    stamina: float    # sprint capacity in seconds

    def copy(self):
        return Genome(self.speed, self.stamina)


def random_genome(s, species):
    """A fresh genome drawn uniformly from the species' spawn ranges."""
    if species == "predator":
        return Genome(
            speed=random.uniform(s.pred_speed_min, s.pred_speed_max),
            stamina=random.uniform(s.pred_stamina_min, s.pred_stamina_max),
        )
    return Genome(
        speed=random.uniform(s.prey_speed_min, s.prey_speed_max),
        stamina=random.uniform(s.prey_stamina_min, s.prey_stamina_max),
    )


def crossover(a, b):
    """Blend two parents. Each gene is an independent random interpolation
    between the parents' values (so siblings differ)."""
    t1 = random.random()
    t2 = random.random()
    return Genome(
        speed=a.speed * t1 + b.speed * (1.0 - t1),
        stamina=a.stamina * t2 + b.stamina * (1.0 - t2),
    )


def mutate(g, s):
    """Apply Gaussian mutation scaled by the global mutation_rate, in place."""
    rate = s.mutation_rate
    if rate > 0:
        g.speed += random.gauss(0.0, rate * SPEED_MUT_SPAN * 0.5)
        g.stamina += random.gauss(0.0, rate * STAMINA_MUT_SPAN * 0.5)
    g.speed = clamp(g.speed, *SPEED_HARD)
    g.stamina = clamp(g.stamina, *STAMINA_HARD)
    return g
