#!/usr/bin/env python3
# A simple unit test example. Replace by your own tests

import importlib.util
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("ece650-a1.py")
SPEC = importlib.util.spec_from_file_location("ece650_a1", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
assignment = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assignment
SPEC.loader.exec_module(assignment)


def point(x, y):
    return assignment.Point(Fraction(x), Fraction(y))


class ParserTests(unittest.TestCase):
    def test_add_accepts_flexible_whitespace_and_negative_coordinates(self):
        command = assignment.parse_command('  add   "Weber   Street"   (2, -1)   (2,2)  ')
        self.assertEqual(command.operation, "add")
        self.assertEqual(command.street, "weber   street")
        self.assertEqual(command.points, (point(2, -1), point(2, 2)))

    def test_street_name_whitespace_is_significant_but_case_is_not(self):
        single_space = assignment.parse_command('add "Weber Street" (0,0) (1,1)')
        double_space = assignment.parse_command('add "weber  street" (0,0) (1,1)')
        different_case = assignment.parse_command('add "WEBER STREET" (0,0) (1,1)')
        self.assertNotEqual(single_space.street, double_space.street)
        self.assertEqual(single_space.street, different_case.street)

    def test_rejects_bad_coordinate_list(self):
        with self.assertRaises(assignment.InputError):
            assignment.parse_command('add "Bad Street" (1,2) garbage (3,4)')

    def test_rejects_zero_length_segment(self):
        with self.assertRaises(assignment.InputError):
            assignment.parse_command('add "Bad Street" (1,2) (1,2)')


class GeometryTests(unittest.TestCase):
    def test_fractional_crossing(self):
        first = assignment.Segment(point(0, 0), point(3, 3))
        second = assignment.Segment(point(0, 2), point(3, 0))
        self.assertEqual(
            assignment.segment_intersections(first, second),
            {assignment.Point(Fraction(6, 5), Fraction(6, 5))},
        )

    def test_parallel_segments_do_not_intersect(self):
        first = assignment.Segment(point(0, 0), point(2, 0))
        second = assignment.Segment(point(0, 1), point(2, 1))
        self.assertEqual(assignment.segment_intersections(first, second), set())

    def test_collinear_overlap_returns_overlap_boundaries(self):
        first = assignment.Segment(point(0, 0), point(4, 0))
        second = assignment.Segment(point(2, 0), point(6, 0))
        self.assertEqual(
            assignment.segment_intersections(first, second),
            {point(2, 0), point(4, 0)},
        )


class GraphTests(unittest.TestCase):
    def build_sample_graph(self):
        graph = assignment.StreetGraph()
        commands = [
            'add "Weber Street" (2,-1) (2,2) (5,5) (5,6) (3,8)',
            'add "King Street S" (4,2) (4,8)',
            'add "Davenport Road" (1,4) (5,8)',
        ]
        for line in commands:
            graph.execute(assignment.parse_command(line))
        return graph

    def test_sample_has_expected_vertices_and_edges(self):
        graph = self.build_sample_graph()
        vertices, edges = graph.build_graph()

        expected_points = {
            point(2, 2), point(4, 2), point(4, 4), point(5, 5), point(1, 4),
            point(4, 7), point(5, 6), point(5, 8), point(3, 8), point(4, 8),
        }
        self.assertEqual(set(vertices.values()), expected_points)

        expected_edge_points = {
            frozenset((point(2, 2), point(4, 4))),
            frozenset((point(4, 2), point(4, 4))),
            frozenset((point(4, 4), point(5, 5))),
            frozenset((point(4, 4), point(4, 7))),
            frozenset((point(5, 6), point(4, 7))),
            frozenset((point(4, 7), point(1, 4))),
            frozenset((point(3, 8), point(4, 7))),
            frozenset((point(4, 7), point(5, 8))),
            frozenset((point(4, 7), point(4, 8))),
        }
        actual_edge_points = {
            frozenset((vertices[first], vertices[second])) for first, second in edges
        }
        self.assertEqual(actual_edge_points, expected_edge_points)

    def test_modify_and_remove(self):
        graph = self.build_sample_graph()
        graph.build_graph()
        graph.execute(assignment.parse_command('mod "Weber Street" (2,1) (2,2)'))
        vertices, edges = graph.build_graph()
        self.assertEqual(
            set(vertices.values()),
            {point(4, 2), point(1, 4), point(4, 7), point(5, 8), point(4, 8)},
        )
        self.assertEqual(len(edges), 4)

        graph.execute(assignment.parse_command('rm "King Street S"'))
        vertices, edges = graph.build_graph()
        self.assertEqual(vertices, {})
        self.assertEqual(edges, set())

    def test_duplicate_and_missing_street_errors_do_not_change_state(self):
        graph = assignment.StreetGraph()
        graph.execute(assignment.parse_command('add "A Street" (0,0) (1,1)'))
        with self.assertRaisesRegex(
            assignment.InputError, r"^street currently exists\.$"
        ):
            graph.execute(assignment.parse_command('add "a street" (0,1) (1,0)'))
        with self.assertRaises(assignment.InputError):
            graph.execute(assignment.parse_command('mod "Missing" (0,1) (1,0)'))
        with self.assertRaises(assignment.InputError):
            graph.execute(assignment.parse_command('rm "Missing"'))
        self.assertEqual(len(graph.streets), 1)


class IntegrationTests(unittest.TestCase):
    def test_error_goes_to_stderr_and_processing_continues(self):
        input_text = "\n".join(
            [
                'mod "Missing" (0,0) (1,1)',
                'add "First" (0,0) (2,2)',
                'add "Second" (0,2) (2,0)',
                "gg",
                "",
            ]
        )
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH)],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stderr.startswith("Error:"))
        self.assertIn("V = {", result.stdout)
        self.assertIn("E = {", result.stdout)
        self.assertIn("(1.00,1.00)", result.stdout)

    def test_fractional_coordinates_are_printed_to_two_decimal_places(self):
        input_text = "\n".join(
            [
                'add "First" (0,0) (3,3)',
                'add "Second" (0,2) (3,0)',
                "gg",
                "",
            ]
        )
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH)],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("(1.20,1.20)", result.stdout)


if __name__ == "__main__":
    unittest.main()
