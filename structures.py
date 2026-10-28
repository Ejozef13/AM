"""Bounded, explicit JSON encodings and Python nodes for generated exercises."""
STRUCTURE_TYPES = ('linked_list', 'tree', 'graph')


def validate_structure(value, kind):
    key = 'adjacency' if kind == 'graph' else 'values'
    if not isinstance(value, dict) or set(value) != {'__type',key} or value['__type'] != kind:
        raise ValueError(f'{kind} needs {{"__type":"{kind}","{key}":[...]}}.')
    values = value[key]
    if not isinstance(values, list) or len(values) > (24 if kind == 'graph' else 127 if kind == 'tree' else 100):
        raise ValueError(f'{kind} exceeds its size limit.')
    if kind == 'graph':
        for neighbors in values:
            if (not isinstance(neighbors,list) or len(neighbors)>24 or
                any(type(node) is not int or not 0 <= node < len(values) for node in neighbors)):
                raise ValueError('Graph adjacency must contain valid integer node IDs, at most 24 neighbors per node.')
    else:
        for index, item in enumerate(values):
            if kind == 'tree' and item is None:
                continue
            if type(item) is not int or not -(2**31) <= item < 2**31:
                raise ValueError('Node values must be signed 32-bit integers.')
            if kind == 'tree' and index and values[(index-1)//2] is None:
                raise ValueError('Heap-indexed trees cannot contain a child of a null parent.')
        if kind == 'tree' and values and values[-1] is None:
            raise ValueError('Use [] for an empty tree and trim trailing nulls.')
    return value


def validate_tagged(value):
    if isinstance(value, dict):
        if '__type' in value:
            if value['__type'] not in STRUCTURE_TYPES:
                raise ValueError('Unknown structured input type.')
            validate_structure(value,value['__type'])
        else:
            for item in value.values(): validate_tagged(item)
    elif isinstance(value,list):
        for item in value: validate_tagged(item)


class ListNode:
    def __init__(self, val=0, next=None):
        self.val, self.next = val, next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val, self.left, self.right = val, left, right


class Graph:
    def __init__(self, adjacency):
        self.adj = adjacency


def decode(value):
    if isinstance(value,list): return [decode(item) for item in value]
    if not isinstance(value,dict): return value
    kind = value.get('__type')
    if kind not in STRUCTURE_TYPES: return {key:decode(item) for key,item in value.items()}
    validate_structure(value,kind)
    if kind == 'graph': return Graph([list(row) for row in value['adjacency']])
    values = value['values']
    if kind == 'linked_list':
        head = None
        for item in reversed(values): head = ListNode(item,head)
        return head
    nodes = [None if item is None else TreeNode(item) for item in values]
    for i,node in enumerate(nodes):
        if node:
            node.left = nodes[2*i+1] if 2*i+1<len(nodes) else None
            node.right = nodes[2*i+2] if 2*i+2<len(nodes) else None
    return nodes[0] if nodes else None


def encode_structure(value, kind):
    if kind == 'graph':
        return validate_structure({'__type':kind,'adjacency':value.adj},kind)
    values, seen = [], set()
    if kind == 'linked_list':
        while value is not None:
            if id(value) in seen or len(values)>=100: raise ValueError('List became cyclic or too large.')
            seen.add(id(value)); values.append(value.val); value=value.next
    else:
        queue = [(value,0)]
        while queue:
            node,index = queue.pop(0)
            if node is None: continue
            if index>=127 or id(node) in seen: raise ValueError('Tree became cyclic or too large.')
            seen.add(id(node))
            while len(values)<=index: values.append(None)
            values[index]=node.val
            queue.extend([(node.left,2*index+1),(node.right,2*index+2)])
    return validate_structure({'__type':kind,'values':values},kind)


def encode(value, original=None):
    if isinstance(original,dict) and original.get('__type') in STRUCTURE_TYPES:
        return encode_structure(value,original['__type'])
    if isinstance(value,ListNode): return encode_structure(value,'linked_list')
    if isinstance(value,TreeNode): return encode_structure(value,'tree')
    if isinstance(value,Graph): return encode_structure(value,'graph')
    if isinstance(value,list):
        return [encode(item,original[i] if isinstance(original,list) and i<len(original) else None) for i,item in enumerate(value)]
    if isinstance(value,dict): return {key:encode(item) for key,item in value.items()}
    return value


STRUCTURE_GUIDE = (
    'Structured inputs use explicit tagged JSON: linked_list={"__type":"linked_list","values":[1,2]}, '
    'tree={"__type":"tree","values":[1,null,2]} with HEAP indices left=2*i+1/right=2*i+2 (not compact BFS), '
    'graph={"__type":"graph","adjacency":[[1],[0]]}. Graphs may have cycles and disconnected vertices; IDs are 0..n-1. '
    'Limits: list 100 nodes, tree 127 heap slots, graph 24 vertices and 24 neighbors per vertex; node values int32. '
    'Empty structures use empty arrays. Trees must trim trailing nulls and have no child under a null parent. '
    'Runners supply ListNode fields val/next, TreeNode fields val/left/right, and Graph adjacency rows. Do not redefine these types. '
    'Use null/None for empty list/tree heads; never dereference them. State encodings explicitly in the question. '
)
