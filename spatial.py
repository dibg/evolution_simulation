"""A uniform spatial-hash grid for fast neighbour queries.

Rebuilt every simulation step. Lets each creature look up nearby prey / flowers
/ mates without scanning the whole population (avoids O(n^2) per frame).
"""


class SpatialGrid:
    def __init__(self, cell):
        self.cell = max(8.0, float(cell))
        self.cells = {}

    def _key(self, x, y):
        return (int(x // self.cell), int(y // self.cell))

    def insert(self, item, x, y):
        self.cells.setdefault(self._key(x, y), []).append(item)

    def query(self, x, y, radius):
        """Return all items in cells overlapping the circle (x, y, radius).
        This is a superset — the caller still checks exact distance."""
        r = int(radius // self.cell) + 1
        cx = int(x // self.cell)
        cy = int(y // self.cell)
        out = []
        get = self.cells.get
        for gx in range(cx - r, cx + r + 1):
            for gy in range(cy - r, cy + r + 1):
                bucket = get((gx, gy))
                if bucket:
                    out.extend(bucket)
        return out
