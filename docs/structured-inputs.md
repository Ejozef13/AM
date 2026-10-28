# Linked lists, trees, and graphs

The runners now construct real linked-list/tree nodes and graph adjacency
objects for Python, Java, C, and C++. Types are supplied by the trusted harness;
generated/student source implements the required function without redefining
node types. Expected answers never enter the compiled harness.

## Serialized inputs

| Kind | JSON example | Limit |
| --- | --- | --- |
| `linked_list` | `{"__type":"linked_list","values":[1,2]}` | 100 integer nodes; acyclic |
| `tree` | `{"__type":"tree","values":[1,null,2]}` | 127 heap-indexed slots |
| `graph` | `{"__type":"graph","adjacency":[[1],[0],[]]}` | 24 vertices, at most 24 neighbors per vertex |

Node values are signed 32-bit integers. Empty structures use empty arrays.
Trees use **heap indices**, left `2*i+1`, right `2*i+2`; this is not the compact
BFS notation used on some interview sites. No child can have a null parent, and
trailing nulls must be trimmed. Graph IDs are indices `0..n-1`; directed edges,
self-loops, cycles, and disconnected vertices are representable. Weighted edges
and arbitrary object payloads are not supported.

## Language interfaces

| Language | Nodes | Graph |
| --- | --- | --- |
| Python | `ListNode.val/next`, `TreeNode.val/left/right` | `Graph.adj`: list of neighbor lists |
| Java | `ListNode`, `TreeNode`, with `int val` and node links | `Graph.adj`: `int[][]` |
| C | `const ListNode *`, `const TreeNode *` | `const Graph *`, with `size`, `degree[24]`, `adj[24][24]` |
| C++ | `const ListNode *`, `const TreeNode *` | `const Graph *`, with `std::vector<std::vector<int>> adj` |

Java methods remain inside `public class Solution`. C/C++ source contains a free
`solve` function without `main`. Array parameters still have their earlier calling
convention. A structured input is one logical JSON argument, even when a C array
parameter expands into a pointer and length.

Python decodes the tagged inputs before calling the function. It can serialize
returned node/graph objects too; `None` remains JSON null, so empty structured
returns must have explicitly specified behavior. Native structure types are
currently **input-only**: return a scalar or an allowed integer array (C scalar
returns only). These contracts support traversal/search/counting questions but
are not an unrestricted clone of every interview platform's node API.

Input mutation is detected by serializing the post-call structures. List/tree
cycles and excessive growth are rejected by bounded serializers. Graph topology
may naturally contain cycles; adjacency rows are compared to the original input.
C/C++ still use sanitizers and container limits. Bad pointers are runtime errors,
not accepted wrong-answer bugs. Generated starters must be executable on every
checked case while producing a wrong answer on at least one.

## Real verification

```bash
sudo -v
env AM_STRUCTURE_TESTS=1 python -m unittest discover -s tests -p test_structures.py -v
```

Use `AM_DOCKER_DIRECT=1` only if already authorized for direct Docker access.
The optional matrix checks nonempty inputs, empty structures, and mutation in
all four languages. Normal regression checks also reject invalid encodings and
round-trip sparse trees, cyclic graphs, and empty structures.
