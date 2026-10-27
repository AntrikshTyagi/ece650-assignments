#!/usr/bin/env python3
"""Unit tests for ece650-a1.py."""
import importlib.util
import os
import subprocess
import sys
import unittest
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "ece650-a1.py")


def load_script():
    """Import ece650-a1.py (its name has a dash, so a plain import won't do)."""
    spec = importlib.util.spec_from_file_location("a1", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["a1"] = module
    spec.loader.exec_module(module)
    return module


a1 = load_script()


def P(x, y):
    return (Fraction(x), Fraction(y))


def run_script(*lines):
    """Feed lines to the script on stdin; return the finished process."""
    return subprocess.run([sys.executable, SCRIPT], input="\n".join(lines) + "\n",
                          capture_output=True, text=True)


def db_from(*lines):
    db = a1.StreetDB()
    for line in lines:
        a1.process(line, db)
    return db


SAMPLE = (
    'add "Weber Street" (2,-1) (2,2) (5,5) (5,6) (3,8)',
    'add "King Street S" (4,2) (4,8)',
    'add "Davenport Road" (1,4) (5,8)',
)


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

class TestParsing(unittest.TestCase):
    def test_extra_whitespace_and_negative_numbers(self):
        cmd, key, pts = a1.parse_line('  add   "Weber   Street"   (2, -1)   (2,2)  ')
        self.assertEqual(cmd, "add")
        self.assertEqual(key, "weber   street")
        self.assertEqual(pts, [P(2, -1), P(2, 2)])

    def test_name_ignores_case_but_keeps_spacing(self):
        key = lambda name: a1.parse_line('add "%s" (0,0) (1,1)' % name)[1]
        self.assertEqual(key("Weber Street"), key("WEBER STREET"))
        self.assertNotEqual(key("Weber Street"), key("weber  street"))

    def test_invalid_input_is_rejected(self):
        bad_lines = {
            "junk between coordinates": 'add "Bad Street" (1,2) garbage (3,4)',
            "repeated point": 'add "Bad Street" (1,2) (1,2)',
            "single point": 'add "Bad Street" (1,2)',
            "empty name": 'add "" (1,2) (3,4)',
            "unknown command": 'move "Bad Street" (1,2) (3,4)',
        }
        for why, line in bad_lines.items():
            with self.subTest(why), self.assertRaises(a1.InputError):
                a1.parse_line(line)


# ---------------------------------------------------------------------------
# Segment intersection
# ---------------------------------------------------------------------------

class TestIntersect(unittest.TestCase):
    def test_crossing_at_a_fractional_point(self):
        hits = a1.intersect(P(0, 0), P(3, 3), P(0, 2), P(3, 0))
        self.assertEqual(hits, {P(Fraction(6, 5), Fraction(6, 5))})

    def test_parallel_lines_never_meet(self):
        self.assertFalse(a1.intersect(P(0, 0), P(2, 0), P(0, 1), P(2, 1)))

    def test_overlap_gives_both_ends_of_shared_part(self):
        hits = a1.intersect(P(0, 0), P(4, 0), P(2, 0), P(6, 0))
        self.assertEqual(hits, {P(2, 0), P(4, 0)})


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def graph_points(db):
    """Return (vertex points, edges as pairs of points) for the current graph."""
    vertices, edges = db.build_graph()
    where = dict(vertices)
    return set(where.values()), {frozenset((where[u], where[v])) for u, v in edges}


class TestGraph(unittest.TestCase):
    def test_assignment_example(self):
        points, edges = graph_points(db_from(*SAMPLE))
        self.assertEqual(points, {
            P(2, 2), P(4, 2), P(4, 4), P(5, 5), P(1, 4),
            P(4, 7), P(5, 6), P(5, 8), P(3, 8), P(4, 8),
        })
        expected = [
            (P(2, 2), P(4, 4)), (P(4, 2), P(4, 4)), (P(4, 4), P(5, 5)),
            (P(4, 4), P(4, 7)), (P(5, 6), P(4, 7)), (P(4, 7), P(1, 4)),
            (P(3, 8), P(4, 7)), (P(4, 7), P(5, 8)), (P(4, 7), P(4, 8)),
        ]
        self.assertEqual(edges, {frozenset(e) for e in expected})

    def test_graph_follows_mod_and_rm(self):
        db = db_from(*SAMPLE)
        db.build_graph()

        a1.process('mod "Weber Street" (2,1) (2,2)', db)
        points, edges = graph_points(db)
        self.assertEqual(points, {P(4, 2), P(1, 4), P(4, 7), P(5, 8), P(4, 8)})
        self.assertEqual(len(edges), 4)

        a1.process('rm "King Street S"', db)
        self.assertEqual(db.build_graph(), ([], []))

    def test_rejected_commands_leave_database_alone(self):
        db = db_from('add "A Street" (0,0) (1,1)')
        failing = {
            'add "a street" (0,1) (1,0)': "street currently exists.",
            'mod "Missing" (0,1) (1,0)': "cannot modify a street that does not exist",
            'rm "Missing"': "cannot remove a street that does not exist",
        }
        for line, message in failing.items():
            with self.subTest(line):
                with self.assertRaises(a1.InputError) as ctx:
                    a1.process(line, db)
                self.assertEqual(str(ctx.exception), message)
        self.assertEqual(list(db.streets), ["a street"])


# ---------------------------------------------------------------------------
# Whole program over stdin/stdout
# ---------------------------------------------------------------------------

class TestProgram(unittest.TestCase):
    def test_keeps_going_after_an_error(self):
        result = run_script('mod "Missing" (0,0) (1,1)',
                            'add "First" (0,0) (2,2)',
                            'add "Second" (0,2) (2,0)',
                            "gg")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stderr.startswith("Error:"))
        for piece in ("V = {", "E = {", "(1.00,1.00)"):
            self.assertIn(piece, result.stdout)

    def test_two_decimal_output(self):
        result = run_script('add "First" (0,0) (3,3)',
                            'add "Second" (0,2) (3,0)',
                            "gg")
        self.assertEqual(result.returncode, 0)
        self.assertIn("(1.20,1.20)", result.stdout)


if __name__ == "__main__":
    unittest.main()
