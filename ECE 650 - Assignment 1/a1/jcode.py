#!/usr/bin/env python3
"""ECE 650 Assignment 1: construct a street-intersection graph."""

import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


class InputError(ValueError):
    """An error caused by an invalid user command."""


@dataclass(frozen=True, order=True)
class Point:
    x: Fraction
    y: Fraction


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point


@dataclass(frozen=True)
class Command:
    operation: str
    street: Optional[str] = None
    points: Tuple[Point, ...] = ()


ADD_MOD_RE = re.compile(r'^\s*(add|mod)\s*"([^"]+)"(.*)$')
RM_RE = re.compile(r'^\s*rm\s*"([^"]+)"\s*$')
GG_RE = re.compile(r'^\s*gg\s*$')
COORD_RE = re.compile(
    r'\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)'
)


def normalize_street_name(name: str) -> str:
    """Make street lookup case-insensitive while preserving whitespace."""

    if name == "":
        raise InputError("street name cannot be empty")

    return name.casefold()


def parse_points(text: str) -> Tuple[Point, ...]:
    """Parse a sequence of integer coordinate pairs."""

    points: List[Point] = []
    position = 0

    for match in COORD_RE.finditer(text):
        separator = text[position:match.start()]

        # Empty separation and whitespace-only separation are both valid.
        if separator and not separator.isspace():
            raise InputError("invalid coordinate list")

        x = Fraction(int(match.group(1)))
        y = Fraction(int(match.group(2)))
        points.append(Point(x, y))

        position = match.end()

    # Reject any unparsed text after the last coordinate.
    if text[position:].strip():
        raise InputError("invalid coordinate list")

    if len(points) < 2:
        raise InputError("a street must contain at least two points")

    if any(
        first == second
        for first, second in zip(points, points[1:])
    ):
        raise InputError(
            "a street cannot contain a zero-length line segment"
        )

    return tuple(points)


def parse_command(line: str) -> Command:
    """Parse one input line without changing program state."""

    if GG_RE.fullmatch(line):
        return Command("gg")

    rm_match = RM_RE.fullmatch(line)

    if rm_match:
        street_name = normalize_street_name(rm_match.group(1))
        return Command("rm", street_name)

    add_mod_match = ADD_MOD_RE.fullmatch(line)

    if add_mod_match:
        operation, raw_name, coordinate_text = add_mod_match.groups()

        return Command(
            operation,
            normalize_street_name(raw_name),
            parse_points(coordinate_text),
        )

    raise InputError("invalid command")


def cross(
    ax: Fraction,
    ay: Fraction,
    bx: Fraction,
    by: Fraction,
) -> Fraction:
    """Calculate the two-dimensional cross product."""

    return ax * by - ay * bx


def point_on_segment(point: Point, segment: Segment) -> bool:
    """Check whether a point lies on a closed line segment."""

    dx1 = point.x - segment.start.x
    dy1 = point.y - segment.start.y
    dx2 = segment.end.x - segment.start.x
    dy2 = segment.end.y - segment.start.y

    if cross(dx1, dy1, dx2, dy2) != 0:
        return False

    return (
        min(segment.start.x, segment.end.x)
        <= point.x
        <= max(segment.start.x, segment.end.x)
        and min(segment.start.y, segment.end.y)
        <= point.y
        <= max(segment.start.y, segment.end.y)
    )


def segment_intersections(
    first: Segment,
    second: Segment,
) -> Set[Point]:
    """Return the intersection points of two closed segments."""

    px = first.start.x
    py = first.start.y
    qx = second.start.x
    qy = second.start.y

    rx = first.end.x - first.start.x
    ry = first.end.y - first.start.y
    sx = second.end.x - second.start.x
    sy = second.end.y - second.start.y

    denominator = cross(rx, ry, sx, sy)

    q_minus_p_x = qx - px
    q_minus_p_y = qy - py

    # The segments are not parallel.
    if denominator != 0:
        t = (
            cross(q_minus_p_x, q_minus_p_y, sx, sy)
            / denominator
        )
        u = (
            cross(q_minus_p_x, q_minus_p_y, rx, ry)
            / denominator
        )

        if 0 <= t <= 1 and 0 <= u <= 1:
            intersection = Point(
                px + t * rx,
                py + t * ry,
            )
            return {intersection}

        return set()

    # The segments are parallel but not collinear.
    if cross(q_minus_p_x, q_minus_p_y, rx, ry) != 0:
        return set()

    # Handle shared endpoints or collinear overlap boundaries.
    candidates = {
        first.start,
        first.end,
        second.start,
        second.end,
    }

    return {
        point
        for point in candidates
        if point_on_segment(point, first)
        and point_on_segment(point, second)
    }


def street_segments(
    points: Sequence[Point],
) -> Iterable[Tuple[int, Segment]]:
    """Generate all consecutive segments of a street."""

    for index in range(len(points) - 1):
        yield index, Segment(
            points[index],
            points[index + 1],
        )


def position_on_segment(
    point: Point,
    segment: Segment,
) -> Fraction:
    """Return a parameter used to order points on a segment."""

    dx = segment.end.x - segment.start.x

    if dx != 0:
        return (point.x - segment.start.x) / dx

    return (
        (point.y - segment.start.y)
        / (segment.end.y - segment.start.y)
    )


class StreetGraph:
    """Store streets and construct their intersection graph."""

    def __init__(self) -> None:
        self.streets: Dict[str, Tuple[Point, ...]] = {}
        self.vertex_ids: Dict[Point, int] = {}

    def execute(self, command: Command) -> Optional[str]:
        """Execute one parsed command."""

        if command.operation == "add":
            assert command.street is not None

            if command.street in self.streets:
                raise InputError("street currently exists.")

            self.streets[command.street] = command.points
            return None

        if command.operation == "mod":
            assert command.street is not None

            if command.street not in self.streets:
                raise InputError(
                    "cannot modify a street that does not exist"
                )

            self.streets[command.street] = command.points
            return None

        if command.operation == "rm":
            assert command.street is not None

            if command.street not in self.streets:
                raise InputError(
                    "cannot remove a street that does not exist"
                )

            del self.streets[command.street]
            return None

        if command.operation == "gg":
            vertices, edges = self.build_graph()
            return format_graph(vertices, edges)

        raise InputError("unsupported command")

    def build_graph(
        self,
    ) -> Tuple[Dict[int, Point], Set[Tuple[int, int]]]:
        """Construct the graph from intersections of different streets."""

        active_points: Dict[
            Tuple[str, int],
            Set[Point],
        ] = defaultdict(set)

        intersections: Set[Point] = set()
        street_items = list(self.streets.items())

        for (
            (first_name, first_points),
            (second_name, second_points),
        ) in combinations(street_items, 2):

            for first_index, first_segment in street_segments(
                first_points
            ):
                for second_index, second_segment in street_segments(
                    second_points
                ):
                    crossing_points = segment_intersections(
                        first_segment,
                        second_segment,
                    )

                    if not crossing_points:
                        continue

                    intersections.update(crossing_points)

                    active_points[
                        (first_name, first_index)
                    ].update(
                        {
                            first_segment.start,
                            first_segment.end,
                            *crossing_points,
                        }
                    )

                    active_points[
                        (second_name, second_index)
                    ].update(
                        {
                            second_segment.start,
                            second_segment.end,
                            *crossing_points,
                        }
                    )

        current_points: Set[Point] = set()

        for points in active_points.values():
            current_points.update(points)

        for point in sorted(current_points):
            if point not in self.vertex_ids:
                self.vertex_ids[point] = (
                    len(self.vertex_ids) + 1
                )

        vertices = {
            self.vertex_ids[point]: point
            for point in current_points
        }

        edges: Set[Tuple[int, int]] = set()

        for (
            street_name,
            segment_index,
        ), points in active_points.items():

            street_points = self.streets[street_name]

            segment = Segment(
                street_points[segment_index],
                street_points[segment_index + 1],
            )

            ordered = sorted(
                points,
                key=lambda point: position_on_segment(
                    point,
                    segment,
                ),
            )

            for first_point, second_point in zip(
                ordered,
                ordered[1:],
            ):
                if first_point == second_point:
                    continue

                if (
                    first_point not in intersections
                    and second_point not in intersections
                ):
                    continue

                first_id = self.vertex_ids[first_point]
                second_id = self.vertex_ids[second_point]

                edges.add(
                    tuple(sorted((first_id, second_id)))
                )

        return vertices, edges


def format_fraction(value: Fraction) -> str:
    """Format a rational value with exactly two decimal places."""

    with localcontext() as context:
        context.prec = 50

        decimal_value = (
            Decimal(value.numerator)
            / Decimal(value.denominator)
        )

        return format(decimal_value, ".2f")


def format_point(point: Point) -> str:
    """Format a point for graph output."""

    return (
        f"({format_fraction(point.x)},"
        f"{format_fraction(point.y)})"
    )


def format_graph(
    vertices: Dict[int, Point],
    edges: Set[Tuple[int, int]],
) -> str:
    """Format the graph using the required V and E representation."""

    lines = ["V = {"]

    vertex_items = sorted(vertices.items())

    for index, (vertex_id, point) in enumerate(vertex_items):
        comma = (
            ","
            if index < len(vertex_items) - 1
            else ""
        )

        lines.append(
            f"  {vertex_id}: {format_point(point)}{comma}"
        )

    lines.append("}")
    lines.append("E = {")

    edge_items = sorted(edges)

    for index, (first_id, second_id) in enumerate(edge_items):
        comma = (
            ","
            if index < len(edge_items) - 1
            else ""
        )

        lines.append(
            f"  <{first_id},{second_id}>{comma}"
        )

    lines.append("}")

    return "\n".join(lines)


def main() -> int:
    """Read and process commands from standard input."""

    graph = StreetGraph()

    for line in sys.stdin:
        # Ignore blank or whitespace-only lines.
        if not line.strip():
            continue

        try:
            command = parse_command(
                line.rstrip("\r\n")
            )

            output = graph.execute(command)

            if output is not None:
                print(output, flush=True)

        except InputError as error:
            print(
                f"Error: {error}",
                file=sys.stderr,
                flush=True,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())