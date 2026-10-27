// Unit tests for ece650-a2, using doctest.
//
// ece650-a2.cpp is included directly with ECE650_A2_TESTING defined, so its
// main() is left out and the tests can feed input to processLine() and look
// at stdout and stderr separately.

#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include "doctest.h"

#define ECE650_A2_TESTING
#include "ece650-a2.cpp"

#include <set>

namespace {

struct Output {
    std::vector<std::string> out;  // lines written to stdout
    std::vector<std::string> err;  // lines written to stderr
};

std::vector<std::string> splitLines(const std::string& text) {
    std::vector<std::string> lines;
    std::istringstream in(text);
    std::string line;
    while (std::getline(in, line)) {
        lines.push_back(line);
    }
    return lines;
}

// Feeds a whole session through the program, the same way main() does.
Output run(const std::string& input) {
    Graph g;
    std::ostringstream out, err;
    std::istringstream in(input);
    std::string line;
    while (std::getline(in, line)) {
        processLine(line, g, out, err);
    }
    return {splitLines(out.str()), splitLines(err.str())};
}

// The spec only fixes the "Error:" prefix, so that's all we check for.
bool allErrors(const std::vector<std::string>& lines) {
    for (const auto& l : lines) {
        if (l.rfind("Error:", 0) != 0) {
            return false;
        }
    }
    return true;
}

}  // namespace

// ---------------------------------------------------------------------------
// Basic paths and the errors named in the handout
// ---------------------------------------------------------------------------

TEST_CASE("paths that have only one shortest answer") {
    // a branch at 1 where the 4-5 side is a dead end
    CHECK(run("V 7\nE {<1,2>,<2,3>,<3,6>,<1,4>,<4,5>,<6,7>}\ns 1 7\n").out ==
          std::vector<std::string>{"1-2-3-6-7"});

    // a ring of 10 where going one way round is clearly shorter
    const std::string ring =
        "V 10\nE {<1,2>,<2,3>,<3,4>,<4,5>,<1,6>,<6,7>,<7,8>,<8,9>,<9,10>,<10,5>}\n";
    CHECK(run(ring + "s 1 5\n").out == std::vector<std::string>{"1-2-3-4-5"});
    CHECK(run(ring + "s 9 3\n").out == std::vector<std::string>{"9-10-5-4-3"});
}

TEST_CASE("edge to a vertex that doesn't exist") {
    Output r = run("V 4\nE {<1,2>,<2,7>}\n");
    CHECK(r.out.empty());
    REQUIRE(r.err.size() == 1);
    CHECK(allErrors(r.err));
}

TEST_CASE("no path between two components") {
    Output r = run("V 6\nE {<1,2>,<2,3>,<4,5>,<5,6>}\ns 1 6\n");
    CHECK(r.out.empty());
    CHECK(r.err.size() == 1);
    CHECK(allErrors(r.err));
}

TEST_CASE("a space inside the edge list doesn't lose edges") {
    // the spec says this won't happen, but reading with >> used to drop
    // everything after the space, so keep a check for it
    Output r = run("V 6\nE {<1,2>, <2,3>,<3,4>}\ns 1 4\n");
    CHECK(r.out == std::vector<std::string>{"1-2-3-4"});
    CHECK(r.err.empty());
}

TEST_CASE("sample run from the handout") {
    Output r = run("V 15\nE {<2,6>,<2,8>,<2,5>,<6,5>,<5,8>,<6,10>,<10,8>}\ns 2 10\n"
                   "V 5\nE {<1,3>,<3,2>,<3,4>,<4,5>,<5,2>}\ns 5 1\n");
    REQUIRE(r.out.size() == 2);
    CHECK(r.err.empty());
    // both queries have two shortest paths and either one is allowed
    CHECK(std::set<std::string>{"2-8-10", "2-6-10"}.count(r.out[0]) == 1);
    CHECK(std::set<std::string>{"5-2-3-1", "5-4-3-1"}.count(r.out[1]) == 1);
}

// ---------------------------------------------------------------------------
// Cases from the clarifications page
// ---------------------------------------------------------------------------

TEST_CASE("s v v prints v, even for an isolated vertex") {
    CHECK(run("V 3\nE {<1,2>,<2,3>}\ns 2 2\n").out == std::vector<std::string>{"2"});
    CHECK(run("V 4\nE {<1,2>}\ns 4 4\n").out == std::vector<std::string>{"4"});
}

TEST_CASE("query vertex outside 1..V, including 0 and negatives") {
    Output r = run("V 3\nE {<1,2>,<2,3>}\ns 1 4\ns 0 2\ns -1 2\n");
    CHECK(r.out.empty());
    CHECK(r.err.size() == 3);
    CHECK(allErrors(r.err));
}

TEST_CASE("E {} is an error but the vertices can still be used") {
    Output r = run("V 3\nE {}\ns 2 2\n");
    CHECK(r.err.size() == 1);
    CHECK(allErrors(r.err));
    CHECK(r.out == std::vector<std::string>{"2"});
}

TEST_CASE("V 0, V 1 and negative V are errors and the program keeps going") {
    for (const char* bad : {"V 0\n", "V 1\n", "V -4\n"}) {
        Output r = run(std::string(bad) + "V 2\nE {<1,2>}\ns 1 2\n");
        CHECK(r.err.size() == 1);
        CHECK(allErrors(r.err));
        CHECK(r.out == std::vector<std::string>{"1-2"});
    }
}

TEST_CASE("edge endpoints of 0 or below are errors") {
    CHECK(run("V 3\nE {<-1,2>}\n").err.size() == 1);
    CHECK(run("V 3\nE {<0,2>}\n").err.size() == 1);
}

TEST_CASE("a bad E keeps none of its edges, and a new V starts over") {
    Output r = run("V 3\nE {<1,2>,<1,4>}\ns 1 2\nV 2\nE {<1,2>}\ns 1 2\n");
    CHECK(r.err.size() == 2);  // the bad edge, then "no path" for 1 to 2
    CHECK(allErrors(r.err));
    CHECK(r.out == std::vector<std::string>{"1-2"});
}

TEST_CASE("a new V forgets the old edges") {
    Output r = run("V 3\nE {<1,2>,<2,3>}\ns 1 3\nV 3\nE {<1,2>}\ns 1 3\n");
    CHECK(r.out == std::vector<std::string>{"1-2-3"});
    CHECK(r.err.size() == 1);
}

TEST_CASE("self-loops and duplicate edges don't break anything") {
    CHECK(run("V 3\nE {<1,1>,<1,2>,<2,2>,<2,3>}\ns 1 3\n").out ==
          std::vector<std::string>{"1-2-3"});
    CHECK(run("V 3\nE {<1,2>,<1,2>,<2,1>,<2,3>}\ns 3 1\n").out ==
          std::vector<std::string>{"3-2-1"});
}

// ---------------------------------------------------------------------------
// Other things worth checking
// ---------------------------------------------------------------------------

TEST_CASE("numbers too big for long long give an error instead of a crash") {
    CHECK(run("V 99999999999999999999\n").err.size() == 1);
    CHECK(run("V 3\nE {<1,99999999999999999999>}\n").err.size() == 1);
}

TEST_CASE("query or edges before any valid V") {
    CHECK(allErrors(run("s 1 2\n").err));
    Output r = run("V 1\nE {<1,2>}\n");
    CHECK(r.err.size() == 2);
}

TEST_CASE("unknown command") {
    Output r = run("x 1 2\n");
    CHECK(r.out.empty());
    CHECK(r.err.size() == 1);
}

TEST_CASE("last line without a newline still gets an answer") {
    CHECK(run("V 2\nE {<1,2>}\ns 1 2").out == std::vector<std::string>{"1-2"});
}

TEST_CASE("large V with only a few edges") {
    CHECK(run("V 5000000\nE {<1,4999999>,<4999999,5000000>}\ns 1 5000000\n").out ==
          std::vector<std::string>{"1-4999999-5000000"});
}

TEST_CASE("Graph::shortestPath on its own") {
    Graph g;
    g.reset(6);
    g.setEdges({{1, 2}, {2, 3}, {3, 4}, {4, 5}, {5, 6}});
    CHECK(g.shortestPath(6, 1) == std::vector<Graph::Vertex>{6, 5, 4, 3, 2, 1});
    CHECK(g.shortestPath(3, 3) == std::vector<Graph::Vertex>{3});

    g.clearEdges();
    CHECK(g.shortestPath(1, 6).empty());
    CHECK(g.isValidVertex(6));
    CHECK_FALSE(g.isValidVertex(7));
}
