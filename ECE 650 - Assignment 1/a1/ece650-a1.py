#!/usr/bin/env python3
"""ECE 650 Assignment 1: street database -> intersection graph."""
import sys
from collections import defaultdict
from decimal import ROUND_HALF_EVEN, Context, Decimal
from fractions import Fraction

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class InputError(Exception):
    pass


def street_key(name):
    """Streets are looked up case-insensitively; spacing is kept as typed."""
    if name == "":
        raise InputError("street name cannot be empty")
    return name.casefold()


def skip_ws(text, i):
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def read_int(text, i):
    """Read an optionally signed integer at text[i]. Return (value, next) or None."""
    start = i
    if i < len(text) and text[i] in "+-":
        i += 1
    first_digit = i
    while i < len(text) and text[i].isdecimal():
        i += 1
    if i == first_digit:
        return None
    return int(text[start:i]), i


def read_coordinate(text, i):
    """Read '( x , y )' at text[i]. Return ((x, y), next) or None."""
    if i >= len(text) or text[i] != "(":
        return None
    got = read_int(text, skip_ws(text, i + 1))
    if got is None:
        return None
    x, i = got
    i = skip_ws(text, i)
    if i >= len(text) or text[i] != ",":
        return None
    got = read_int(text, skip_ws(text, i + 1))
    if got is None:
        return None
    y, i = got
    i = skip_ws(text, i)
    if i >= len(text) or text[i] != ")":
        return None
    return (Fraction(x), Fraction(y)), i + 1


def parse_points(text):
    """Parse '(x1,y1) (x2,y2)...' (spaces between pairs optional)."""
    pts = []
    i = skip_ws(text, 0)
    while i < len(text):
        got = read_coordinate(text, i)
        if got is None:
            raise InputError("invalid coordinate list")
        p, i = got
        pts.append(p)
        i = skip_ws(text, i)

    if len(pts) < 2:
        raise InputError("a street must contain at least two points")
    for p, q in zip(pts, pts[1:]):
        if p == q:
            raise InputError("a street cannot contain a zero-length line segment")
    return pts


def parse_line(line):
    """Return (command, street key, points) for one line, or raise InputError."""
    if line.strip() == "gg":
        return "gg", None, None

    body = line[skip_ws(line, 0):]
    cmd = next((c for c in ("add", "mod", "rm") if body.startswith(c)), None)
    if cmd is None:
        raise InputError("invalid command")

    rest = body[skip_ws(body, len(cmd)):]
    close = rest.find('"', 1) if rest.startswith('"') else -1
    if close <= 1:  # no opening/closing quote, or an empty name
        raise InputError("invalid command")
    key = street_key(rest[1:close])
    tail = rest[close + 1:]

    if cmd == "rm":
        if tail.strip() != "":
            raise InputError("invalid command")
        return cmd, key, None
    return cmd, key, parse_points(tail)


# ---------------------------------------------------------------------------
# Geometry (exact arithmetic with Fractions)
# ---------------------------------------------------------------------------

def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def on_segment(p, a, b):
    """True if point p lies on the closed segment ab."""
    if cross(a, b, p) != 0:
        return False
    return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def intersect(p1, p2, p3, p4):
    """Return the set of intersection points of segments p1p2 and p3p4.

    For collinear overlapping segments, the endpoints of the overlap are
    returned.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if denom != 0:
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / denom
        if 0 <= t <= 1 and 0 <= u <= 1:
            return {(x1 + t * (x2 - x1), y1 + t * (y2 - y1))}
        return set()
    # Parallel: intersect only if collinear and overlapping.
    if cross(p1, p2, p3) != 0:
        return set()
    return {p for p in (p1, p2, p3, p4)
            if on_segment(p, p1, p2) and on_segment(p, p3, p4)}


def segments_of(pts):
    return list(zip(pts, pts[1:]))


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class StreetDB:
    def __init__(self):
        self.streets = {}      # key -> [points]
        self.ids = {}          # point -> vertex id (stable across gg calls)

    def add(self, key, pts):
        if key in self.streets:
            raise InputError("street currently exists.")
        self.streets[key] = pts

    def mod(self, key, pts):
        if key not in self.streets:
            raise InputError("cannot modify a street that does not exist")
        self.streets[key] = pts

    def rm(self, key):
        if key not in self.streets:
            raise InputError("cannot remove a street that does not exist")
        del self.streets[key]

    def build_graph(self):
        # Points of interest on every segment that meets another street,
        # keyed by (street, segment index).
        marked = defaultdict(set)
        crossings = set()
        names = list(self.streets)
        for i, s1 in enumerate(names):
            for s2 in names[i + 1:]:
                for j, (a, b) in enumerate(segments_of(self.streets[s1])):
                    for k, (c, d) in enumerate(segments_of(self.streets[s2])):
                        hits = intersect(a, b, c, d)
                        if not hits:
                            continue
                        crossings |= hits
                        marked[(s1, j)].update(hits, (a, b))
                        marked[(s2, k)].update(hits, (c, d))

        present = set().union(*marked.values())
        for p in sorted(present):
            if p not in self.ids:
                self.ids[p] = len(self.ids) + 1

        # Edges: along each marked segment, connect consecutive points if at
        # least one of the pair is an intersection.
        edges = set()
        for (name, j), pts in marked.items():
            a, b = self.streets[name][j], self.streets[name][j + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ordered = sorted(pts, key=lambda p: (p[0] - a[0]) * dx + (p[1] - a[1]) * dy)
            for p, q in zip(ordered, ordered[1:]):
                if p in crossings or q in crossings:
                    u, v = self.ids[p], self.ids[q]
                    edges.add((min(u, v), max(u, v)))

        vertices = sorted((self.ids[p], p) for p in present)
        return vertices, sorted(edges)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

TWO_PLACES = Decimal("0.01")
EXACT = Context(prec=50, rounding=ROUND_HALF_EVEN)


def fmt_num(v):
    q = EXACT.divide(Decimal(v.numerator), Decimal(v.denominator))
    return str(EXACT.quantize(q, TWO_PLACES))


def block(label, entries):
    body = ",\n".join("  " + e for e in entries)
    return label + " = {\n" + (body + "\n" if body else "") + "}"


def render_graph(db):
    vertices, edges = db.build_graph()
    v_lines = ["{}: ({},{})".format(vid, fmt_num(p[0]), fmt_num(p[1]))
               for vid, p in vertices]
    e_lines = ["<{},{}>".format(u, v) for u, v in edges]
    return block("V", v_lines) + "\n" + block("E", e_lines)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def process(line, db):
    cmd, key, pts = parse_line(line)
    if cmd == "gg":
        print(render_graph(db), flush=True)
    elif cmd == "add":
        db.add(key, pts)
    elif cmd == "mod":
        db.mod(key, pts)
    else:
        db.rm(key)


def main():
    db = StreetDB()
    for line in sys.stdin:
        if line.strip() == "":
            continue
        try:
            process(line.rstrip("\r\n"), db)
        except InputError as e:
            print("Error: " + str(e), file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
