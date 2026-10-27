"""Compare program output with expected output, ignoring vertex numbering
and ordering: each graph is reduced to its vertex coordinates and its edges
expressed as coordinate pairs."""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROG = HERE.parent / "a1" / "ece650-a1.py"


def parse_graphs(text):
    graphs = []
    for v_block, e_block in re.findall(r"V = \{(.*?)\}\s*E = \{(.*?)\}", text, re.S):
        coords = dict(re.findall(r"(\w+):\s*(\([^)]*\))", v_block))
        edges = {frozenset((coords[a], coords[b]))
                 for a, b in re.findall(r"<(\w+),(\w+)>", e_block)}
        graphs.append((set(coords.values()), edges))
    return graphs


def main():
    inp = (HERE / "sample_input.txt").read_text()
    res = subprocess.run([sys.executable, str(PROG)], input=inp,
                         capture_output=True, text=True, timeout=10)
    got = parse_graphs(res.stdout)
    want = parse_graphs((HERE / "expected_output.txt").read_text())
    ok = res.returncode == 0 and not res.stderr and len(got) == len(want)
    for i, (g, w) in enumerate(zip(got, want), 1):
        match = g == w
        ok &= match
        print(f"gg #{i}: {'PASS' if match else 'FAIL'} "
              f"({len(g[0])} vertices, {len(g[1])} edges)")
        if not match:
            print("  missing vertices:", w[0] - g[0], " extra:", g[0] - w[0])
            print("  missing edges:", w[1] - g[1], " extra:", g[1] - w[1])
    if res.stderr:
        print("stderr:", res.stderr)
    print("ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
