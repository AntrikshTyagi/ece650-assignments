"""Tests for other-code-test/ece650-a1.py. Doesn't touch ../a1."""
import random
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
THEIRS = HERE / (sys.argv[1] if len(sys.argv) > 1 else "ece650-a1.py")
OURS = HERE.parent / "a1" / "ece650-a1.py"


def run(prog, text):
    r = subprocess.run([sys.executable, str(prog)], input=text,
                       capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout, r.stderr


def graphs(text, normalize):
    out = []
    for vb, eb in re.findall(r"V = \{(.*?)\}\s*E = \{(.*?)\}", text, re.S):
        coords = {}
        for vid, x, y in re.findall(r"(\w+):\s*\(([^,]+),([^)]+)\)", vb):
            coords[vid] = (round(float(x), 2), round(float(y), 2)) if normalize else (x, y)
        edges = {frozenset((coords[a], coords[b])) for a, b in re.findall(r"<(\w+),(\w+)>", eb)}
        out.append((set(coords.values()), edges))
    return out


section = lambda t: print("\n=== " + t)

# 1. sample
section("1. Sample input")
code, out, err = run(THEIRS, (HERE.parent / "tests" / "sample_input.txt").read_text())
want_text = (HERE.parent / "tests" / "expected_output.txt").read_text()
exact = graphs(out, False) == graphs(want_text, False)
structural = graphs(out, True) == graphs(want_text, True)
print("exit code:", code, "| stderr:", repr(err))
print("same graph, ignoring number format:", structural)
print("same coordinate text as the PDF (e.g. (2,2)):", exact)
first_v = re.search(r"V = \{\n(.*?)\n", out).group(1)
print("first vertex line printed:", first_v.strip())

# 2. error / edge cases, one line each on top of a valid street
section("2. Error and edge cases (one per run, after a valid add)")
cases = [
    ('add "A" (1,1) (2,2)', "duplicate add"),
    ('mod "Nope" (1,1) (2,2)', "mod unknown street"),
    ('rm "Nope"', "rm unknown street"),
    ('add "B" (1,1)', "one point"),
    ('add "B" (1,1) (1,1)', "repeated consecutive point"),
    ('add "B" (0,0) (1,1) (0,0)', "street revisits an earlier point (not consecutive)"),
    ('add "B"(0,4) (4,0)', "no space after name"),
    ('add "B" (0,4)(4,0)', "no space between points"),
    ('add"B" (0,4) (4,0)', "no space after command"),
    ('add B (0,4) (4,0)', "no quotes"),
    ('add "B (0,4) (4,0)', "missing closing quote"),
    ('add "B1" (0,4) (4,0)', "digit in name"),
    ('add "B#!" (0,4) (4,0)', "punctuation in name"),
    ('add "" (0,0) (1,1)', "empty name"),
    ('add "   " (0,0) (1,1)', "blank name"),
    ('add "B" 0,4 4,0', "no brackets"),
    ('add "B" (0,4) (4,0', "missing )"),
    ('add "B" (0,4,1) (4,0)', "three numbers"),
    ('add "B" (1.5,2) (3,3)', "decimal coordinate"),
    ('add "B" (+1,4) (4,0)', "plus sign"),
    ('add "B" (²,4) (4,0)', "unicode digit"),
    ('add "B"', "no coordinates"),
    ('add', "bare add"),
    ('rm "A" extra', "rm with extra text"),
    ('gg extra', "gg with argument"),
    ('GG', "upper-case GG"),
    ('Add "B" (0,4) (4,0)', "capitalised Add"),
    ('foo', "unknown command"),
    ('123', "line starting with digits"),
    ('add "a" (0,4) (4,0)', "same name, different case"),
    ('add "A " (0,4) (4,0)', "same name plus trailing space"),
    ('add "B  Street" (0,4) (4,0)\nadd "B Street" (0,5) (5,0)', "double space vs single space names"),
]
print(f"{'case':52} {'theirs':40} ours")
for line, label in cases:
    text = 'add "A" (0,0) (4,4)\n' + line + "\n"
    r1 = run(THEIRS, text)
    r2 = run(OURS, text)
    def summary(r):
        if r[0] != 0:
            return "CRASH exit %d" % r[0]
        errs = [l for l in r[2].splitlines() if l.startswith("Error")]
        return ("ERROR: " + errs[0][7:])[:38] if errs else "accepted"
    print(f"{label:52} {summary(r1):40} {summary(r2)}")

# 3. stdout must contain only graphs
section("3. Errors go only to stderr")
code, out, err = run(THEIRS, 'rm "x"\nfoo\nadd "A" (0,0) (2,2)\nadd "B" (0,2) (2,0)\ngg\n')
print("'Error' in stdout:", "Error" in out, "| errors on stderr:", err.count("Error"))

# 4. vertex numbering across gg
section("4. Vertex numbering across gg calls")
code, out, err = run(THEIRS, 'add "A" (0,0) (4,4)\nadd "B" (0,4) (4,0)\ngg\n'
                             'add "C" (-5,-5) (-5,5)\nadd "D" (-6,0) (-4,0)\ngg\n')
ids = re.findall(r"(\d+): \(([^)]*)\)", out)
first = {c: v for v, c in ids[:5]}
second = {c: v for v, c in ids[5:]}
changed = {c: (first[c], second[c]) for c in first if first[c] != second.get(c)}
print("points whose number changed after adding streets:", changed or "none")

# 5. randomized comparison against our program
section("5. Randomized comparison with ../a1 (graphs compared by coordinates)")
random.seed(650)
mismatches = 0
crashes = 0
N = 400
for trial in range(N):
    lines = []
    names = []
    for _ in range(random.randint(2, 7)):
        k = random.randint(2, 5)
        pts = []
        while len(pts) < k:
            p = (random.randint(-6, 6), random.randint(-6, 6))
            if p not in pts:
                pts.append(p)
        name = "S" + "abcdefghij"[len(names)]
        names.append(name)
        lines.append(f'add "{name}" ' + " ".join(f"({x},{y})" for x, y in pts))
    if random.random() < 0.4:
        lines.append(f'rm "{random.choice(names)}"')
    lines.append("gg")
    text = "\n".join(lines) + "\n"
    a, b = run(THEIRS, text), run(OURS, text)
    if a[0] != 0:
        crashes += 1
    if graphs(a[1], True) != graphs(b[1], True):
        mismatches += 1
        if mismatches <= 2:
            print("--- mismatch input:\n" + text)
print(f"{N} random inputs: {mismatches} graph mismatches, {crashes} crashes")

# 6. speed
section("6. Speed with 60 streets")
random.seed(1)
lines = []
for i in range(60):
    pts = [(random.randint(-50, 50), random.randint(-50, 50)) for _ in range(5)]
    pts = list(dict.fromkeys(pts))
    lines.append('add "S' + "".join(chr(97 + int(d)) for d in str(i)) + '" ' +
                 " ".join(f"({x},{y})" for x, y in pts))
lines.append("gg")
import time
t = time.time()
code, out, err = run(THEIRS, "\n".join(lines) + "\n")
v = len(graphs(out, True)[0][0])
print(f"exit {code}, {v} vertices, {time.time() - t:.2f}s")
