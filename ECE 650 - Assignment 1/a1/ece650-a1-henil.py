#!/usr/bin/env python3

import sys
import re
from fractions import Fraction


def subtract(p1, p2):
    return (p1[0] - p2[0], p1[1] - p2[1])


def cross_product(v1, v2):
    return v1[0] * v2[1] - v1[1] * v2[0]


def is_point_on_segment(pt, seg_start, seg_end):
    # Check collinearity via cross product
    v_seg = subtract(seg_end, seg_start)
    v_pt = subtract(pt, seg_start)
    if cross_product(v_seg, v_pt) != 0:
        return False

    # Check bounding box
    min_x, max_x = min(seg_start[0], seg_end[0]), max(seg_start[0], seg_end[0])
    min_y, max_y = min(seg_start[1], seg_end[1]), max(seg_start[1], seg_end[1])
    return min_x <= pt[0] <= max_x and min_y <= pt[1] <= max_y


def segment_intersection(p1, p2, p3, p4):
    """
    Find intersection between segment p1-p2 and segment p3-p4.
    Returns a set of points (empty, or containing 1 point).
    All points use Fraction for exact coordinates.
    """
    r = subtract(p2, p1)
    s = subtract(p4, p3)
    ca = subtract(p3, p1)

    denom = cross_product(r, s)

    if denom != 0:
        t = Fraction(cross_product(ca, s), denom)
        u = Fraction(cross_product(ca, r), denom)

        if 0 <= t <= 1 and 0 <= u <= 1:
            ix = Fraction(p1[0]) + t * r[0]
            iy = Fraction(p1[1]) + t * r[1]
            return {(ix, iy)}
        return set()

    # Parallel and collinear check
    if cross_product(ca, r) != 0:
        return set()

    # Collinear segments: return shared endpoint if any
    shared = set()
    for pt in (p1, p2, p3, p4):
        fpt = (Fraction(pt[0]), Fraction(pt[1]))
        if is_point_on_segment(fpt, p1, p2) and is_point_on_segment(fpt, p3, p4):
            shared.add(fpt)
    return shared


def get_position_ratio(pt, seg_start, seg_end):
    """Return relative position of pt along seg_start -> seg_end (between 0 and 1)."""
    dx = seg_end[0] - seg_start[0]
    dy = seg_end[1] - seg_start[1]
    if dx != 0:
        return (pt[0] - seg_start[0]) / dx
    return (pt[1] - seg_start[1]) / dy


def parse_command(line):
    """
    Parses a single line of input.
    Returns (cmd, street_name, points).
    Raises ValueError on invalid syntax.
    """
    line = line.strip()
    if not line:
        return None

    tokens = line.split(None, 1)
    cmd = tokens[0]

    if cmd not in ("add", "mod", "rm", "gg"):
        raise ValueError(f"unrecognized command '{cmd}'")

    if cmd == "gg":
        if len(tokens) > 1:
            raise ValueError("gg takes no arguments")
        return cmd, None, None

    if len(tokens) == 1:
        raise ValueError(f"'{cmd}' requires arguments")

    rest = tokens[1].strip()

    # Street name must start with double quote
    if not rest.startswith('"'):
        raise ValueError("street name must be enclosed in double quotes")

    closing_quote = rest.find('"', 1)
    if closing_quote == -1:
        raise ValueError("unterminated street name")

    name = rest[1:closing_quote]
    if not name:
        raise ValueError("street name cannot be empty")

    remainder = rest[closing_quote + 1:].strip()

    if cmd == "rm":
        if remainder:
            raise ValueError("rm takes only a street name")
        return cmd, name, None

    # For add and mod, street name cannot contain internal quotes
    if '"' in remainder:
        raise ValueError("invalid street name or extra quotes")

    # Parse coordinates: (x, y)
    coord_pattern = re.compile(r'\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)')
    points = []
    idx = 0
    rem_len = len(remainder)

    while idx < rem_len:
        while idx < rem_len and remainder[idx].isspace():
            idx += 1
        if idx == rem_len:
            break

        match = coord_pattern.match(remainder, idx)
        if not match:
            raise ValueError("invalid coordinates format")

        points.append((int(match.group(1)), int(match.group(2))))
        idx = match.end()

    if len(points) < 2:
        raise ValueError("street requires at least two coordinates")

    for i in range(len(points) - 1):
        if points[i] == points[i + 1]:
            raise ValueError("consecutive coordinates must differ")

    return cmd, name, points


def generate_graph(streets):
    street_keys = list(streets.keys())
    intersections = set()
    segment_intersections_map = {}

    for k in street_keys:
        pts = streets[k]
        for i in range(len(pts) - 1):
            segment_intersections_map[(k, i)] = set()

    # Compare every pair of streets
    for i in range(len(street_keys)):
        for j in range(i + 1, len(street_keys)):
            name1, name2 = street_keys[i], street_keys[j]
            pts1, pts2 = streets[name1], streets[name2]

            for s1 in range(len(pts1) - 1):
                p1, p2 = pts1[s1], pts1[s1 + 1]
                for s2 in range(len(pts2) - 1):
                    p3, p4 = pts2[s2], pts2[s2 + 1]

                    hits = segment_intersection(p1, p2, p3, p4)
                    for pt in hits:
                        intersections.add(pt)
                        segment_intersections_map[(name1, s1)].add(pt)
                        segment_intersections_map[(name2, s2)].add(pt)

    # Vertices = all intersections + endpoints of segments that have an intersection
    vertices = set(intersections)
    for (name, s_idx), hits in segment_intersections_map.items():
        if hits:
            pts = streets[name]
            p_start = (Fraction(pts[s_idx][0]), Fraction(pts[s_idx][1]))
            p_end = (Fraction(pts[s_idx + 1][0]), Fraction(pts[s_idx + 1][1]))
            vertices.add(p_start)
            vertices.add(p_end)

    sorted_vertices = sorted(vertices, key=lambda p: (p[0], p[1]))
    vertex_ids = {pt: i + 1 for i, pt in enumerate(sorted_vertices)}

    # Build edges along each segment
    edges = set()
    for name, pts in streets.items():
        for i in range(len(pts) - 1):
            seg_start = (Fraction(pts[i][0]), Fraction(pts[i][1]))
            seg_end = (Fraction(pts[i + 1][0]), Fraction(pts[i + 1][1]))

            # Find all vertices on this segment
            pts_on_seg = [
                pt for pt in vertices
                if is_point_on_segment(pt, seg_start, seg_end)
            ]

            if len(pts_on_seg) < 2:
                continue

            pts_on_seg.sort(key=lambda pt: get_position_ratio(pt, seg_start, seg_end))

            for k in range(len(pts_on_seg) - 1):
                u_pt = pts_on_seg[k]
                v_pt = pts_on_seg[k + 1]
                if u_pt == v_pt:
                    continue

                if u_pt in intersections or v_pt in intersections:
                    uid = vertex_ids[u_pt]
                    vid = vertex_ids[v_pt]
                    edges.add((min(uid, vid), max(uid, vid)))

    # Output V
    def format_coord(val):
        num = round(float(val), 2)
        if num == 0.0:
            num = 0.0
        return f"{num:.2f}"

    print("V = {")
    for pt in sorted_vertices:
        vid = vertex_ids[pt]
        print(f"  {vid}: ({format_coord(pt[0])},{format_coord(pt[1])})")
    print("}")

    # Output E
    edge_lines = [f"  <{u},{v}>" for u, v in sorted(edges)]
    print("E = {")
    if edge_lines:
        print(",\n".join(edge_lines))
    print("}")


def main():
    streets = {}

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
        except (EOFError, KeyboardInterrupt):
            break

        try:
            parsed = parse_command(line)
            if parsed is None:
                continue

            cmd, name, points = parsed

            if cmd == "add":
                key = name.lower()
                if key in streets:
                    raise ValueError("street currently exists.")
                streets[key] = points

            elif cmd == "mod":
                key = name.lower()
                if key not in streets:
                    raise ValueError("'mod' or 'rm' specified for a street that does not exist.")
                streets[key] = points

            elif cmd == "rm":
                key = name.lower()
                if key not in streets:
                    raise ValueError("'mod' or 'rm' specified for a street that does not exist.")
                del streets[key]

            elif cmd == "gg":
                generate_graph(streets)

        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()