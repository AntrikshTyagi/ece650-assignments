"""Test suite for a1/ece650-a1.py.

Covers the sample from the assignment, the manual and error cases from the
"Testing" section of the walkthrough, and one or more checks for every choice
in its "Assumptions about ambiguous requirements" table.

Run:  python3 tests/test_a1.py
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROG = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "a1" / "ece650-a1.py"

results = []   # (section, name, passed, detail)
section = ""


# ---------------------------------------------------------------- helpers

def run(text):
    r = subprocess.run([sys.executable, str(PROG)], input=text,
                       capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout, r.stderr


def graphs(stdout):
    """Each gg block as (ids, vertices, edges).

    ids:      {"(2,2)": 1, ...}  coordinate text -> vertex number
    vertices: set of coordinate texts, exactly as printed
    edges:    set of frozensets of two coordinate texts
    """
    out = []
    for vb, eb in re.findall(r"V = \{\n(.*?)\}\nE = \{\n(.*?)\}", stdout, re.S):
        ids = {}
        for num, coord in re.findall(r"^  (\d+): (\([^)]*\))$", vb, re.M):
            ids[coord] = int(num)
        name = {v: k for k, v in ids.items()}
        edges = {frozenset((name[int(a)], name[int(b)]))
                 for a, b in re.findall(r"<(\d+),(\d+)>", eb)}
        out.append((ids, set(ids), edges))
    return out


def E(*pairs):
    return {frozenset(p) for p in pairs}


def errors(stderr):
    return [l[len("Error: "):] for l in stderr.splitlines() if l.startswith("Error: ")]


def check(name, ok, detail=""):
    results.append((section, name, bool(ok), detail))


def check_graph(name, text, vertices, edges, index=-1):
    code, out, err = run(text)
    g = graphs(out)
    if not g:
        check(name, False, "no graph printed; stderr=%r" % err)
        return
    _, v, e = g[index]
    ok = code == 0 and v == set(vertices) and e == edges and not errors(err)
    detail = ""
    if not ok:
        detail = "V got %s, E got %s, errors %s" % (sorted(v), [sorted(x) for x in e], errors(err))
    check(name, ok, detail)


def check_error(name, line, message, setup='add "A" (0,0) (4,4)\n'):
    """`line` must give exactly one error with this message, and the program
    must keep going: a valid gg afterwards still prints the setup graph."""
    text = setup + line + "\nadd \"Z\" (0,4) (4,0)\ngg\n"
    code, out, err = run(text)
    errs = errors(err)
    still_running = len(graphs(out)) == 1
    ok = code == 0 and errs == [message] and still_running and "Error" not in out
    check(name, ok, "" if ok else "errors=%r, graphs=%d, exit=%d" % (errs, len(graphs(out)), code))


def check_accepted(name, line, setup='add "A" (0,0) (4,4)\n'):
    code, out, err = run(setup + line + "\n")
    ok = code == 0 and not errors(err)
    check(name, ok, "" if ok else "errors=%r" % errors(err))


# ================================================================ 1. sample
section = "1. Sample from the assignment"

code, out, err = run((HERE / "sample_input.txt").read_text())
got = graphs(out)
want = graphs((HERE / "expected_output.txt").read_text())
check("three graphs printed", len(got) == 3, "got %d" % len(got))
for i, label in enumerate(["after the three adds", "after mod", "after rm"]):
    if i < len(got):
        check("graph " + label, got[i][1:] == want[i][1:],
              "" if got[i][1:] == want[i][1:] else "V=%s" % sorted(got[i][1]))
check("no errors, exit code 0", code == 0 and err == "")
if len(got) >= 2:
    kept = all(got[0][0][c] == got[1][0][c] for c in got[1][1])
    check("vertices keep their numbers after mod", kept)

# ================================================================ 2. graph cases
section = "2. Graph cases (walkthrough: manual cases)"

check_graph("intersection that isn't a whole number",
            'add "A" (0,0) (3,3)\nadd "B" (0,3) (3,0)\ngg\n',
            ["(0,0)", "(3,3)", "(0,3)", "(3,0)", "(1.50,1.50)"],
            E(("(0,0)", "(1.50,1.50)"), ("(1.50,1.50)", "(3,3)"),
              ("(0,3)", "(1.50,1.50)"), ("(1.50,1.50)", "(3,0)")))

check_graph("two streets overlapping on one line",
            'add "A" (0,0) (4,0)\nadd "B" (2,0) (6,0)\ngg\n',
            ["(0,0)", "(2,0)", "(4,0)", "(6,0)"],
            E(("(0,0)", "(2,0)"), ("(2,0)", "(4,0)"), ("(4,0)", "(6,0)")))

check_graph("streets touching only at an end-point",
            'add "A" (0,0) (2,2)\nadd "B" (2,2) (4,0)\ngg\n',
            ["(0,0)", "(2,2)", "(4,0)"],
            E(("(0,0)", "(2,2)"), ("(2,2)", "(4,0)")))

check_graph("streets that never meet",
            'add "A" (0,0) (1,0)\nadd "B" (0,1) (1,1)\ngg\n', [], set())

check_graph("parallel streets on different lines",
            'add "A" (0,0) (4,0)\nadd "B" (0,1) (4,1)\ngg\n', [], set())

check_graph("extra whitespace everywhere",
            '   add    "Main   St"   ( 1 , 1 )   (5,5)  \nadd "x" (1,5) (5,1)\n  gg  \n',
            ["(1,1)", "(5,5)", "(1,5)", "(5,1)", "(3,3)"],
            E(("(1,1)", "(3,3)"), ("(3,3)", "(5,5)"), ("(1,5)", "(3,3)"), ("(3,3)", "(5,1)")))

check_graph("a segment with no crossing adds no vertices",
            'add "A" (0,0) (2,2) (2,5)\nadd "B" (0,2) (2,0)\ngg\n',
            ["(0,0)", "(2,2)", "(0,2)", "(2,0)", "(1,1)"],
            E(("(0,0)", "(1,1)"), ("(1,1)", "(2,2)"), ("(0,2)", "(1,1)"), ("(1,1)", "(2,0)")))

check_graph("three streets through one point give one vertex",
            'add "A" (0,0) (2,2)\nadd "B" (0,2) (2,0)\nadd "C" (1,0) (1,2)\ngg\n',
            ["(0,0)", "(2,2)", "(0,2)", "(2,0)", "(1,0)", "(1,2)", "(1,1)"],
            E(*[(p, "(1,1)") for p in ["(0,0)", "(2,2)", "(0,2)", "(2,0)", "(1,0)", "(1,2)"]]))

check_graph("blank lines are ignored",
            '\nadd "A" (0,0) (2,2)\n\n   \nadd "B" (0,2) (2,0)\n\ngg\n',
            ["(0,0)", "(2,2)", "(0,2)", "(2,0)", "(1,1)"],
            E(*[(p, "(1,1)") for p in ["(0,0)", "(2,2)", "(0,2)", "(2,0)"]]))

check_graph("rm then gg gives an empty graph",
            'add "A" (0,0) (2,2)\nadd "B" (0,2) (2,0)\nrm "B"\ngg\n', [], set())

# ================================================================ 3. assumptions
section = "3. Assumptions (walkthrough: ambiguous requirements)"

# names are case-insensitive
code, out, err = run('add "Main St" (0,0) (1,1)\nadd "main st" (0,0) (2,2)\n'
                     'mod "MAIN ST" (0,1) (1,0)\nrm "mAiN sT"\ngg\n')
check("names ignore case: add of same name in other case is rejected, mod/rm work",
      errors(err) == ["`add' specified for a street that already exists"]
      and graphs(out) and graphs(out)[0][1] == set(),
      "errors=%r" % errors(err))
code, out, err = run('add "Weber  Street" (0,0) (1,1)\nadd "weber street" (0,0) (2,2)\n')
check("names ignore extra spaces: \"Weber  Street\" = \"weber street\"",
      errors(err) == ["`add' specified for a street that already exists"], "errors=%r" % errors(err))
code, out, err = run('add "A" (0,0) (1,1)\nrm "A "\n')
check("names ignore trailing spaces: rm \"A \" removes \"A\"", errors(err) == [])

# a street crossing itself is not an intersection
check_graph("a street crossing itself creates no vertex",
            'add "A" (0,0) (4,4) (4,0) (0,4)\ngg\n', [], set())
check_graph("self-crossing point stays out even when another street crosses",
            'add "A" (0,0) (4,4) (4,0) (0,4)\nadd "B" (0,1) (1,0)\ngg\n',
            ["(0,0)", "(4,4)", "(0,1)", "(1,0)", "(0.50,0.50)"],
            E(("(0,0)", "(0.50,0.50)"), ("(0.50,0.50)", "(4,4)"),
              ("(0,1)", "(0.50,0.50)"), ("(0.50,0.50)", "(1,0)")))

# vertex numbers: stable, not reused, same point gets its old number back
code, out, err = run('add "A" (0,0) (4,4)\nadd "B" (0,4) (4,0)\ngg\n'
                     'rm "B"\ngg\n'
                     'add "C" (0,4) (4,0)\ngg\n'
                     'add "D" (0,1) (1,0)\ngg\n')
g = graphs(out)
if len(g) == 4:
    first, _, again, more = (x[0] for x in g)
    check("vertex numbers start at 1 and are unique",
          sorted(first.values()) == [1, 2, 3, 4, 5])
    check("same points get their old numbers back after rm and re-add", again == first)
    old_kept = all(more[c] == n for c, n in first.items())
    new_nums = [n for c, n in more.items() if c not in first]
    check("adding a street leaves existing numbers unchanged", old_kept)
    check("new vertices get new numbers, never reused ones",
          new_nums and min(new_nums) > max(first.values()) and
          len(set(more.values())) == len(more), "new=%s" % new_nums)
else:
    check("vertex numbering sequence", False, "expected 4 graphs, got %d" % len(g))

# overlapping streets: ends of the overlap are intersections
check_graph("overlap: one street inside another",
            'add "A" (0,0) (6,0)\nadd "B" (2,0) (4,0)\ngg\n',
            ["(0,0)", "(2,0)", "(4,0)", "(6,0)"],
            E(("(0,0)", "(2,0)"), ("(2,0)", "(4,0)"), ("(4,0)", "(6,0)")))
check_graph("overlap: diagonal streets sharing a stretch",
            'add "A" (0,0) (3,3)\nadd "B" (1,1) (5,5)\ngg\n',
            ["(0,0)", "(1,1)", "(3,3)", "(5,5)"],
            E(("(0,0)", "(1,1)"), ("(1,1)", "(3,3)"), ("(3,3)", "(5,5)")))
check_graph("collinear but not overlapping: no intersection",
            'add "A" (0,0) (1,0)\nadd "B" (2,0) (3,0)\ngg\n', [], set())

# number format
check_graph("whole numbers print without decimals, others with two (2/3 rounds to 0.67)",
            'add "A" (0,0) (2,2)\nadd "B" (0,2) (1,0)\ngg\n',
            ["(0,0)", "(2,2)", "(0,2)", "(1,0)", "(0.67,0.67)"],
            E(("(0,0)", "(0.67,0.67)"), ("(0.67,0.67)", "(2,2)"),
              ("(0,2)", "(0.67,0.67)"), ("(0.67,0.67)", "(1,0)")))
check_graph("negative non-whole coordinates print correctly",
            'add "A" (0,0) (-2,-2)\nadd "B" (0,-2) (-1,0)\ngg\n',
            ["(0,0)", "(-2,-2)", "(0,-2)", "(-1,0)", "(-0.67,-0.67)"],
            E(("(0,0)", "(-0.67,-0.67)"), ("(-0.67,-0.67)", "(-2,-2)"),
              ("(0,-2)", "(-0.67,-0.67)"), ("(-0.67,-0.67)", "(-1,0)")))
check_graph("mixed: one whole, one non-whole coordinate",
            'add "A" (0,0) (4,1)\nadd "B" (2,-1) (2,3)\ngg\n',
            ["(0,0)", "(4,1)", "(2,-1)", "(2,3)", "(2,0.50)"],
            E(("(0,0)", "(2,0.50)"), ("(2,0.50)", "(4,1)"),
              ("(2,-1)", "(2,0.50)"), ("(2,0.50)", "(2,3)")))

# spacing rules
check_error("space required after the command", 'add"B" (0,4) (4,0)', "unknown command `add\"B\"'")
check_error("space required after the name", 'add "B"(0,4) (4,0)',
            "coordinates must be separated by spaces")
check_error("space required between points", 'add "B" (0,4)(4,0)',
            "coordinates must be separated by spaces")
check_accepted("spaces inside brackets are allowed", 'add "B" ( 0 , 4 )   ( 4,0 )')
check_accepted("tabs count as spaces", 'add\t"B"\t(0,4)\t(4,0)')

# name characters
check_accepted("letters and spaces are allowed in names", 'add "King Street S" (0,4) (4,0)')
check_error("digits are not allowed in names", 'add "B1" (0,4) (4,0)',
            "street name may only contain letters and spaces")
check_error("punctuation is not allowed in names", "add \"St. Mary's\" (0,4) (4,0)",
            "street name may only contain letters and spaces")

# repeats
check_accepted("a street may return to an earlier (non-adjacent) point",
               'add "B" (0,4) (4,0) (0,4)')

# ================================================================ 4. errors
section = "4. Error messages (walkthrough: error table)"

ADD_A = 'add "A" (0,0) (4,4)\n'
error_cases = [
    ("add of an existing street", 'add "A" (1,1) (2,2)',
     "`add' specified for a street that already exists"),
    ("mod of an unknown street", 'mod "X" (1,1) (2,2)',
     "`mod' or `rm' specified for a street that does not exist"),
    ("rm of an unknown street", 'rm "X"',
     "`mod' or `rm' specified for a street that does not exist"),
    ("only one coordinate", 'add "B" (1,1)', "a street needs at least two coordinates"),
    ("no coordinates", 'add "B"', "a street needs at least two coordinates"),
    ("same point twice in a row", 'add "B" (1,1) (1,1)',
     "consecutive coordinates of a street must differ"),
    ("no space after the name", 'add "B"(0,4) (4,0)', "coordinates must be separated by spaces"),
    ("no space between points", 'add "B" (0,4)(4,0)', "coordinates must be separated by spaces"),
    ("name without quotes", 'add B (0,4) (4,0)', "street name must be in double quotes"),
    ("missing closing quote", 'add "B (0,4) (4,0)', "missing closing quote on street name"),
    ("digit in the name", 'add "B1" (0,4) (4,0)', "street name may only contain letters and spaces"),
    ("empty name", 'add "" (0,0) (1,1)', "street name cannot be empty"),
    ("name of only spaces", 'add "   " (0,0) (1,1)', "street name cannot be empty"),
    ("coordinates without brackets", 'add "B" 0,4 4,0', "expected '(' at the start of a coordinate"),
    ("missing closing bracket", 'add "B" (0,4) (4,0', "missing ')' in a coordinate"),
    ("three numbers in a coordinate", 'add "B" (0,4,1) (4,0)', "a coordinate must look like (x,y)"),
    ("one number in a coordinate", 'add "B" (0) (4,0)', "a coordinate must look like (x,y)"),
    ("decimal coordinate", 'add "B" (1.5,2) (3,3)', "coordinates must be integers"),
    ("plus sign", 'add "B" (+1,4) (4,0)', "coordinates must be integers"),
    ("non-ASCII digit", 'add "B" (²,4) (4,0)', "coordinates must be integers"),
    ("empty coordinate", 'add "B" (,4) (4,0)', "coordinates must be integers"),
    ("add with nothing after it", "add", "expected a space before the street name"),
    ("rm with nothing after it", "rm", "expected a space before the street name"),
    ("rm with extra text", 'rm "A" extra', "`rm' takes only a street name"),
    ("gg with an argument", "gg extra", "`gg' takes no arguments"),
    ("unknown command", "foo", "unknown command `foo'"),
    ("commands are lower-case only", 'ADD "B" (0,4) (4,0)', "unknown command `ADD'"),
]
for name, line, msg in error_cases:
    check_error(name, line, msg, setup=ADD_A)

# ================================================================ 5. robustness
section = "5. Robustness"

code, out, err = run('rm "x"\nfoo\nadd "A" (0,0) (2,2)\nadd "B" (0,2) (2,0)\ngg\n')
check("errors go to standard error, not standard output",
      "Error" not in out and len(errors(err)) == 2)
check("the program keeps going after errors", len(graphs(out)) == 1)

code, out, err = run('add "A" (0,0) (2,2)\nadd "A" (5,5) (6,6)\nmod "A" (0,0)\n'
                     'add "B" (0,2) (2,0)\ngg\n')
check("a failed add or mod leaves the street unchanged",
      graphs(out) and "(1,1)" in graphs(out)[0][1] and len(errors(err)) == 2)

text = "".join('add "%s" (%d,0) (%d,10)\n' % ("S" + chr(97 + i % 26) * (i // 26 + 1), i, 30 - i)
               for i in range(30)) + "gg\n"
code, out, err = run(text)
check("30 crossing streets: runs and prints a graph", code == 0 and len(graphs(out)) == 1
      and not err)

code, out, err = run("")
check("empty input exits cleanly", code == 0 and out == "" and err == "")


# ================================================================ report
current = None
passed = 0
for sec, name, ok, detail in results:
    if sec != current:
        print("\n" + sec)
        current = sec
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "\n        " + detail))
    passed += ok
print("\n%d of %d tests passed" % (passed, len(results)))
sys.exit(0 if passed == len(results) else 1)
