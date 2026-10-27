// ECE 650 - Assignment 2
//
// Reads V, E and s commands from stdin until EOF and prints a shortest path
// for every s query. Paths go to stdout. Anything wrong goes to stderr as a
// single "Error: ..." line, and then we carry on with the next command.
//
// The file has two halves: the Graph class (storage + BFS) at the top, and
// the code that parses each command and prints results underneath it.
// test.cpp includes this file with ECE650_A2_TESTING defined so that it can
// call processLine() directly without our main() getting in the way.

#include <algorithm>
#include <iostream>
#include <queue>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------

// Undirected, unweighted graph on vertices 1..n.
//
// IDs are long long instead of unsigned on purpose: if "-1" were read into
// an unsigned it would wrap to a huge number and could slip past the range
// check, whereas a signed value just fails it.
class Graph {
public:
    using Vertex = long long;
    using Edge = std::pair<Vertex, Vertex>;

    // Called for a good "V n": n vertices, nothing connected yet.
    void reset(Vertex n) {
        num_vertices_ = n;
        adj_.clear();
    }

    // Used after a bad V so that later E/s commands can't run against the
    // previous graph by accident.
    void invalidate() {
        num_vertices_ = 0;
        adj_.clear();
    }

    bool hasVertices() const { return num_vertices_ > 0; }
    Vertex numVertices() const { return num_vertices_; }
    bool isValidVertex(Vertex v) const { return v >= 1 && v <= num_vertices_; }

    // Replaces the edge set. handleE() has already range-checked everything,
    // so nothing here can fail.
    void setEdges(const std::vector<Edge>& edges) {
        adj_.clear();
        for (const auto& e : edges) {
            if (e.first == e.second) {
                continue;  // a self-loop is never part of a shortest path
            }
            // Neighbours are kept in a set, so <1,2> twice or <1,2> + <2,1>
            // collapse into one edge without any extra checking.
            adj_[e.first].insert(e.second);
            adj_[e.second].insert(e.first);
        }
    }

    void clearEdges() { adj_.clear(); }

    // BFS from src. Returns the path src..dst, or an empty vector when dst
    // can't be reached. Both vertices must already be known to be valid.
    std::vector<Vertex> shortestPath(Vertex src, Vertex dst) const {
        if (src == dst) {
            return {src};  // the clarifications count a single vertex as a path
        }

        // parent[v] is the vertex we reached v from. Having an entry at all
        // means v has been visited, so there's no separate visited set.
        std::unordered_map<Vertex, Vertex> parent;
        std::queue<Vertex> frontier;
        parent[src] = src;
        frontier.push(src);

        bool found = false;
        while (!frontier.empty() && !found) {
            Vertex u = frontier.front();
            frontier.pop();

            auto it = adj_.find(u);
            if (it == adj_.end()) {
                continue;  // u has no edges
            }
            for (Vertex w : it->second) {
                if (parent.count(w)) {
                    continue;
                }
                parent[w] = u;
                // BFS gives w its final distance the moment it is first seen,
                // so we can stop here instead of waiting to dequeue dst.
                if (w == dst) {
                    found = true;
                    break;
                }
                frontier.push(w);
            }
        }

        if (!found) {
            return {};
        }

        // Walk back from dst to src, then flip it round.
        std::vector<Vertex> path;
        for (Vertex v = dst; v != src; v = parent.at(v)) {
            path.push_back(v);
        }
        path.push_back(src);
        std::reverse(path.begin(), path.end());
        return path;
    }

private:
    Vertex num_vertices_ = 0;  // 0 means there is no usable graph

    // Only vertices that actually have edges get an entry, so something like
    // "V 5000000" with a couple of edges costs almost nothing.
    std::unordered_map<Vertex, std::unordered_set<Vertex>> adj_;
};

// ---------------------------------------------------------------------------
// Parsing and running each input line
// ---------------------------------------------------------------------------
// The handlers take the output streams as parameters rather than using
// std::cout/std::cerr directly, which is what lets test.cpp check exactly
// what was printed.

// std::endl flushes, so the user sees the error straight away. The input is
// meant to be interactive, so nothing should sit in a buffer until EOF.
void reportError(std::ostream& err, const std::string& msg) {
    err << "Error: " << msg << std::endl;
}

// Like std::stoll, but the whole string has to be a number ("12x" is
// rejected). Throws std::invalid_argument or std::out_of_range.
Graph::Vertex parseVertex(const std::string& s) {
    std::size_t pos = 0;
    long long v = std::stoll(s, &pos);
    if (pos != s.size()) {
        throw std::invalid_argument("trailing characters");
    }
    return v;
}

// V n
void handleV(std::istringstream& args, Graph& g, std::ostream& err) {
    std::string tok;
    args >> tok;

    // Drop the old graph before even looking at n. If n turns out to be bad
    // we want "no graph", not the previous one.
    g.invalidate();

    Graph::Vertex n = 0;
    try {
        n = parseVertex(tok);
    } catch (const std::exception&) {
        reportError(err, "invalid number of vertices '" + tok + "'");
        return;
    }
    if (n <= 1) {
        reportError(err, "number of vertices must be greater than one");
        return;
    }
    g.reset(n);
}

// E {<a,b>,...}
// All or nothing: if any endpoint is bad we keep no edges at all, otherwise
// later queries would be answered on a graph the user never gave us.
void handleE(std::istringstream& args, Graph& g, std::ostream& err) {
    // Take the rest of the line rather than args >> spec. >> stops at the
    // first space, and an earlier version silently lost edges because of it.
    std::string spec;
    std::getline(args, spec);

    if (!g.hasVertices()) {
        reportError(err, "no valid vertex set defined for edges");
        return;
    }

    // Input is guaranteed to be well formed, so just pick out every <a,b>.
    // The optional '-' lets negative IDs through so they get a proper error.
    static const std::regex edge_re("<(-?[0-9]+),(-?[0-9]+)>");

    std::vector<Graph::Edge> edges;
    for (auto it = std::sregex_iterator(spec.begin(), spec.end(), edge_re);
         it != std::sregex_iterator(); ++it) {
        const std::smatch& m = *it;
        Graph::Vertex a = 0;
        Graph::Vertex b = 0;
        try {
            a = parseVertex(m[1].str());
            b = parseVertex(m[2].str());
        } catch (const std::exception&) {
            // only reachable for numbers too big for a long long
            g.clearEdges();
            reportError(err, "edge " + m[0].str() + " has an invalid vertex");
            return;
        }
        if (!g.isValidVertex(a) || !g.isValidVertex(b)) {
            g.clearEdges();
            reportError(err, "edge " + m[0].str() + " references a vertex outside 1.." +
                                 std::to_string(g.numVertices()));
            return;
        }
        edges.emplace_back(a, b);
    }

    g.setEdges(edges);

    // The clarifications say E {} should ideally be an error. The vertices
    // from V are still fine though, so "s v v" keeps working afterwards.
    if (edges.empty()) {
        reportError(err, "empty edge set");
    }
}

// s a b
void handleS(std::istringstream& args, const Graph& g, std::ostream& out,
             std::ostream& err) {
    std::string tok_a;
    std::string tok_b;
    args >> tok_a >> tok_b;

    if (!g.hasVertices()) {
        reportError(err, "no valid graph defined");
        return;
    }

    Graph::Vertex a = 0;
    Graph::Vertex b = 0;
    try {
        a = parseVertex(tok_a);
        b = parseVertex(tok_b);
    } catch (const std::exception&) {
        reportError(err, "invalid vertex in shortest path query");
        return;
    }
    if (!g.isValidVertex(a) || !g.isValidVertex(b)) {
        reportError(err, "vertex does not exist in the graph (valid range 1.." +
                             std::to_string(g.numVertices()) + ")");
        return;
    }

    std::vector<Graph::Vertex> path = g.shortestPath(a, b);
    if (path.empty()) {
        reportError(err, "no path exists between " + std::to_string(a) + " and " +
                             std::to_string(b));
        return;
    }

    // e.g. 2-8-10, no spaces
    for (std::size_t i = 0; i < path.size(); ++i) {
        if (i > 0) {
            out << '-';
        }
        out << path[i];
    }
    out << std::endl;
}

// Runs one line of input. Blank lines are skipped without a message.
void processLine(const std::string& line, Graph& g, std::ostream& out,
                 std::ostream& err) {
    std::istringstream args(line);
    std::string cmd;
    if (!(args >> cmd)) {
        return;
    }

    if (cmd == "V") {
        handleV(args, g, err);
    } else if (cmd == "E") {
        handleE(args, g, err);
    } else if (cmd == "s") {
        handleS(args, g, out, err);
    } else {
        reportError(err, "unknown command '" + cmd + "'");
    }
}

}  // namespace

#ifndef ECE650_A2_TESTING
int main() {
    Graph g;
    std::string line;

    // getline returns false at EOF, and then we just exit quietly.
    while (std::getline(std::cin, line)) {
        processLine(line, g, std::cout, std::cerr);
    }
    return 0;
}
#endif
