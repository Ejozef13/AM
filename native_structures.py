"""Trusted native node definitions, input builders, and bounded mutation serializers."""
NODE_DEFINITIONS = '''
typedef struct ListNode { int val; struct ListNode *next; } ListNode;
typedef struct TreeNode { int val; struct TreeNode *left; struct TreeNode *right; } TreeNode;
'''
C_GRAPH = 'typedef struct Graph { int size; int degree[24]; int adj[24][24]; } Graph;\n'
CPP_GRAPH = 'struct Graph { std::vector<std::vector<int>> adj; };\n'
JAVA_DEFINITIONS = '''
class ListNode { int val; ListNode next; ListNode(int v) { val=v; } }
class TreeNode { int val; TreeNode left,right; TreeNode(int v) { val=v; } }
class Graph { int[][] adj; Graph(int[][] a) { adj=a; } }
'''
TREE_COLLECT = '''
static int am_collect_tree(const TreeNode *node, int index, int *values, bool *filled,
                           const TreeNode **seen, int *count) {
    if(!node) return 1;
    if(index>=127 || *count>=127) return 0;
    for(int i=0;i<*count;i++) if(seen[i]==node) return 0;
    seen[(*count)++]=node; values[index]=node->val; filled[index]=true;
    return am_collect_tree(node->left,2*index+1,values,filled,seen,count) &&
           am_collect_tree(node->right,2*index+2,values,filled,seen,count);
}
'''
JAVA_SERIALIZERS = r'''
    static String structureJson(Object value) {
        if(value instanceof Graph) {
            int[][] rows=((Graph)value).adj;
            if(rows.length>24) throw new IllegalArgumentException("Graph too large");
            StringBuilder out=new StringBuilder("{\"__type\":\"graph\",\"adjacency\":[");
            for(int i=0;i<rows.length;i++) {
                if(rows[i].length>24) throw new IllegalArgumentException("Graph degree too large");
                if(i>0) out.append(','); out.append(json(rows[i]));
            }
            return out.append("]}").toString();
        }
        String kind=value instanceof ListNode ? "linked_list" : "tree";
        StringBuilder out=new StringBuilder("{\"__type\":\""+kind+"\",\"values\":[");
        java.util.IdentityHashMap<Object,Boolean> seen=new java.util.IdentityHashMap<>();
        if(value instanceof ListNode) {
            ListNode node=(ListNode)value; int count=0;
            while(node!=null) {
                if(count>=100 || seen.put(node,true)!=null) throw new IllegalArgumentException("Cyclic/oversized list");
                if(count++>0) out.append(','); out.append(node.val); node=node.next;
            }
        } else if(value instanceof TreeNode) {
            Integer[] slots=new Integer[127]; fillTree((TreeNode)value,0,slots,seen);
            int end=slots.length; while(end>0 && slots[end-1]==null) end--;
            for(int i=0;i<end;i++) { if(i>0) out.append(','); out.append(slots[i]==null?"null":slots[i]); }
        }
        return out.append("]}").toString();
    }
    static void fillTree(TreeNode node,int index,Integer[] slots,java.util.IdentityHashMap<Object,Boolean> seen) {
        if(node==null) return;
        if(index>=127 || seen.put(node,true)!=null) throw new IllegalArgumentException("Cyclic/oversized tree");
        slots[index]=node.val; fillTree(node.left,2*index+1,slots,seen); fillTree(node.right,2*index+2,slots,seen);
    }
    static String structureArg(Object value,String kind) {
        if(value==null) return "{\"__type\":\""+kind+"\",\"values\":[]}";
        return structureJson(value);
    }
'''


def declarations(language, kind, value, name):
    statements=[]
    if kind == 'graph':
        rows=value['adjacency']
        if language=='java':
            matrix=','.join('new int[]{'+','.join(map(str,row))+'}' for row in rows)
            return [f'Graph {name} = new Graph(new int[][]{{{matrix}}});']
        statements.append(f'Graph {name}_storage = {{}};' if language=='cpp' else f'Graph {name}_storage = {{0}};')
        if language=='cpp':
            matrix=','.join('{'+','.join(map(str,row))+'}' for row in rows)
            statements.append(f'{name}_storage.adj = {{{matrix}}};')
        else:
            statements.append(f'{name}_storage.size = {len(rows)};')
            for i,row in enumerate(rows):
                statements.append(f'{name}_storage.degree[{i}] = {len(row)};')
                for j,node in enumerate(row): statements.append(f'{name}_storage.adj[{i}][{j}] = {node};')
        return statements+[f'const Graph *{name} = &{name}_storage;']
    values=value['values']; type_name='ListNode' if kind=='linked_list' else 'TreeNode'
    if language=='java':
        statements.append(f'{type_name}[] {name}_nodes = new {type_name}[{len(values)}];')
        for i,item in enumerate(values):
            if item is not None: statements.append(f'{name}_nodes[{i}] = new {type_name}({item});')
    else:
        statements.append(f'{type_name} {name}_nodes[{max(1,len(values))}] = {{}};' if language=='cpp' else f'{type_name} {name}_nodes[{max(1,len(values))}] = {{0}};')
        for i,item in enumerate(values):
            if item is not None: statements.append(f'{name}_nodes[{i}].val = {item};')
    for i,item in enumerate(values):
        if item is None: continue
        links=[('next',i+1)] if kind=='linked_list' else [('left',2*i+1),('right',2*i+2)]
        for field,index in links:
            if index<len(values) and values[index] is not None:
                address='' if language=='java' else '&'
                statements.append(f'{name}_nodes[{i}].{field} = {address}{name}_nodes[{index}];')
    first=(f'{name}_nodes[0]' if language=='java' else f'&{name}_nodes[0]') if values else ('null' if language=='java' else 'NULL')
    pointer=type_name if language=='java' else f'const {type_name} *'
    return statements+[f'{pointer} {name} = {first};']


def emit(kind, expression, cpp):
    # Dedicated block scopes let multiple structured arguments share helper names.
    prefix = '{ printf("{\\"__type\\":\\"'+kind+'\\",\\"'+('adjacency' if kind=='graph' else 'values')+'\\":["); '
    if kind=='linked_list':
        body=(f'const ListNode *p={expression}; const ListNode *seen[100]; int n=0; '
              'while(p) { if(n>=100) return 3; for(int i=0;i<n;i++) if(seen[i]==p) return 3; '
              'seen[n]=p; if(n++) printf(","); printf("%d",p->val); p=p->next; }')
    elif kind=='tree':
        body=(f'int values[127]={{0}}; bool filled[127]={{false}}; const TreeNode *seen[127]; int count=0; '
              f'if(!am_collect_tree({expression},0,values,filled,seen,&count)) return 3; '
              'int end=127; while(end>0 && !filled[end-1]) end--; '
              'for(int i=0;i<end;i++) { if(i) printf(","); if(filled[i]) printf("%d",values[i]); else printf("null"); }')
    else:
        size=f'{expression}->adj.size()' if cpp else f'{expression}->size'
        degree=f'{expression}->adj[i].size()' if cpp else f'{expression}->degree[i]'
        body=(f'if(!{expression}) return 3; long n=(long)({size}); if(n<0 || n>24) return 3; '
              f'for(int i=0;i<n;i++) {{ long d=(long)({degree}); if(d<0 || d>24) return 3; '
              'if(i) printf(","); printf("["); '
              f'for(int j=0;j<d;j++) {{ if(j) printf(","); printf("%d",{expression}->adj[i][j]); }} printf("]"); }}')
    return prefix+body+' printf("]}"); }'
