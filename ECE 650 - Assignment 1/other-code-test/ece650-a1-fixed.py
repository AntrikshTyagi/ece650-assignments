#!/usr/bin/env python3
# ECE 650 - A1
# Reads add/mod/rm/gg commands from stdin and prints the street graph.

import re
import sys
from fractions import Fraction


class ParseError(Exception):
    pass


# ---------- parsing ----------

# an integer point like (2,-1); spaces are fine inside the parens
_POINT = r"\(\s*(-?[0-9]+)\s*,\s*(-?[0-9]+)\s*\)"
point_re = re.compile(_POINT)
# every point needs at least one space in front of it
point_list_re = re.compile(r"(?:\s+" + _POINT + r")+\s*")

# a space is required between the command and the name
name_re = re.compile(r'\s+"([^"\n]*)"(.*)', re.DOTALL)
cmd_re = re.compile(r"\s*([A-Za-z]+)(\s.*|)", re.DOTALL)
valid_name_re = re.compile(r"[A-Za-z ]+")


def parse_line(line):
    # None for blank lines, otherwise a tuple that starts with the command
    if not line.strip():
        return None

    m = cmd_re.fullmatch(line)
    if not m:
        raise ParseError("unknown command (expected add, mod, rm or gg)")
    cmd, rest = m.groups()

    if cmd == "gg":
        if rest.strip():
            raise ParseError("gg doesn't take any arguments")
        return ("gg",)

    if cmd in ("add", "mod"):
        name, rest = read_name(cmd, rest)
        return (cmd, name, read_points(rest))

    if cmd == "rm":
        name, rest = read_name(cmd, rest)
        if rest.strip():
            raise ParseError("rm only takes a street name")
        return ("rm", name)

    raise ParseError(f"unknown command '{cmd}' (expected add, mod, rm or gg)")


def read_name(cmd, text):
    m = name_re.match(text)
    if not m:
        raise ParseError(f"{cmd} needs a street name in double quotes")
    name = m.group(1)
    if not name.strip():
        raise ParseError("street name is empty")
    if not valid_name_re.fullmatch(name):
        raise ParseError("street name can only contain letters and spaces")
    # collapse extra spaces so "Weber  St " and "Weber St" are the same street
    return " ".join(name.split()), m.group(2)


def read_points(text):
    if not text.strip():
        raise ParseError("missing coordinates")

    if not point_list_re.fullmatch(text):
        if "." in text:
            raise ParseError("coordinates have to be integers")
        raise ParseError("bad coordinates, expected something like (x1,y1) (x2,y2)")

    pts = [(int(x), int(y)) for x, y in point_re.findall(text)]
    if len(pts) < 2:
        raise ParseError("a street needs at least two points")
    for a, b in zip(pts, pts[1:]):
        if a == b:
            raise ParseError("the same point appears twice in a row")
    return pts


# ---------- street storage ----------

class Streets:
    # street names are case-insensitive, so everything is keyed on name.lower()

    def __init__(self):
        self.data = {}
        self.ids = {}       # point -> vertex number, kept between gg calls
        self.next_id = 1

    def add(self, name, pts):
        key = name.lower()
        if key in self.data:
            raise ParseError("street currently exists")
        self.data[key] = pts

    def mod(self, name, pts):
        key = name.lower()
        if key not in self.data:
            raise ParseError("'mod' or 'rm' specified for a street that does not exist")
        self.data[key] = pts

    def rm(self, name):
        key = name.lower()
        if key not in self.data:
            raise ParseError("'mod' or 'rm' specified for a street that does not exist")
        del self.data[key]

    def segments(self):
        segs = []
        for key, pts in self.data.items():
            for a, b in zip(pts, pts[1:]):
                segs.append((key, a, b))
        return segs


# ---------- geometry ----------
# Everything uses Fraction instead of float. That way, if the same crossing
# gets found from two different segment pairs, the two copies are exactly
# equal and end up as one vertex.

def _between(v, a, b):
    return min(a, b) <= v <= max(a, b)


def _in_box(p, a, b):
    return _between(p[0], a[0], b[0]) and _between(p[1], a[1], b[1])


def _on_segment(p, a, b):
    # p is on segment a-b if it's on the same line and inside the box
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return cross == 0 and _in_box(p, a, b)


def intersect(p1, p2, p3, p4):
    """Where segment p1-p2 meets p3-p4.

    Returns [] if they don't touch, [pt] for a normal crossing, or the two
    ends of the shared piece if they're collinear and overlap.
    """
    x1, y1 = map(Fraction, p1)
    x2, y2 = map(Fraction, p2)
    x3, y3 = map(Fraction, p3)
    x4, y4 = map(Fraction, p4)

    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if d != 0:
        # t and u are how far along each segment the crossing is (0..1)
        t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
        u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
        if 0 <= t <= 1 and 0 <= u <= 1:
            return [(x1 + t * (x2 - x1), y1 + t * (y2 - y1))]
        return []

    # parallel -- only matters if they sit on the same line
    if (x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1) != 0:
        return []

    # collinear: the overlap (if any) starts/ends at some of the 4 endpoints
    a, b, c, e = (x1, y1), (x2, y2), (x3, y3), (x4, y4)
    out = []
    for p in (a, b, c, e):
        if _in_box(p, a, b) and _in_box(p, c, e) and p not in out:
            out.append(p)
    return out


# ---------- building the graph ----------

def build_graph(streets):
    """
    Vertices: every crossing between two different streets, plus both ends
    of any segment that has a crossing on it.
    Edges: consecutive vertices on the same segment, as long as at least
    one of the two is a crossing.
    """
    segs = streets.segments()
    hits = [set() for _ in segs]  # crossings that lie on each segment
    crossings = set()

    for i, (s1, a1, a2) in enumerate(segs):
        for j in range(i + 1, len(segs)):
            s2, b1, b2 = segs[j]
            if s1 == s2:
                continue  # a street doesn't count as crossing itself
            for p in intersect(a1, a2, b1, b2):
                crossings.add(p)
                hits[i].add(p)
                hits[j].add(p)

    # segment ends that become vertices (because their segment has a crossing)
    ends = set()
    for (_, start, end), on_seg in zip(segs, hits):
        if on_seg:
            ends.add((Fraction(start[0]), Fraction(start[1])))
            ends.add((Fraction(end[0]), Fraction(end[1])))
    points = crossings | ends

    edge_pairs = set()
    for (_, start, end), on_seg in zip(segs, hits):
        if not on_seg:
            continue  # nothing crosses it, so this segment adds nothing

        start = (Fraction(start[0]), Fraction(start[1]))
        end = (Fraction(end[0]), Fraction(end[1]))

        # every vertex lying on this segment, not just this segment's own
        # crossings -- otherwise an edge could jump over a vertex that came
        # from somewhere else (a street touching itself, or an overlap)
        on_line = [p for p in points if _on_segment(p, start, end)]

        # line the points up from start to end (projection onto the
        # direction vector -- no sqrt needed since we only sort by it)
        dx, dy = end[0] - start[0], end[1] - start[1]
        chain = sorted(on_line,
                       key=lambda p: (p[0] - start[0]) * dx + (p[1] - start[1]) * dy)

        for p, q in zip(chain, chain[1:]):
            if p in crossings or q in crossings:
                edge_pairs.add(frozenset((p, q)))

    # new points get the next free number; old points keep theirs
    ids = streets.ids
    for p in sorted(points):
        if p not in ids:
            ids[p] = streets.next_id
            streets.next_id += 1
    vertices = {ids[p]: p for p in points}
    edges = {tuple(sorted(ids[p] for p in pair)) for pair in edge_pairs}
    return vertices, edges


# ---------- output ----------

def fmt(v):
    # whole numbers print as-is, like the sample: (2,2)
    if v.denominator == 1:
        return str(v.numerator)
    # only round when printing; TAs asked for python's built-in round()
    s = f"{round(float(v), 2):.2f}"
    return "0.00" if s == "-0.00" else s


def graph_to_text(vertices, edges):
    out = ["V = {"]
    for n in sorted(vertices):
        x, y = vertices[n]
        out.append(f"  {n}: ({fmt(x)},{fmt(y)})")
    out.append("}")

    out.append("E = {")
    if edges:
        # no trailing comma after the last edge
        out.append(",\n".join(f"  <{a},{b}>" for a, b in sorted(edges)))
    out.append("}")
    return "\n".join(out)


def error(msg):
    print(f"Error: {msg}", file=sys.stderr, flush=True)


def main():
    streets = Streets()

    while True:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            break
        if not line:
            break  # EOF

        try:
            cmd = parse_line(line)
            if cmd is None:
                continue

            kind = cmd[0]
            if kind == "add":
                streets.add(cmd[1], cmd[2])
            elif kind == "mod":
                streets.mod(cmd[1], cmd[2])
            elif kind == "rm":
                streets.rm(cmd[1])
            elif kind == "gg":
                print(graph_to_text(*build_graph(streets)), flush=True)
        except ParseError as e:
            error(e)
        except Exception as e:
            # shouldn't happen, but one weird line shouldn't kill the program
            error(f"couldn't process that line ({e})")

    sys.exit(0)


if __name__ == "__main__":
    main()
