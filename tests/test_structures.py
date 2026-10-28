"""Structural encodings plus optional real restricted-container checks."""
import os
from pathlib import Path
import unittest
from code_runner import DockerRunner, grade_case
from compiled_runner import CompiledRunner
from language_contracts import function_header, typed_value
from structures import decode, encode, validate_structure

ARGS = [{'__type':'linked_list','values':[1,2]}, {'__type':'tree','values':[4,None,5]},
        {'__type':'graph','adjacency':[[1],[0]]}]
EMPTY = [{'__type':'linked_list','values':[]}, {'__type':'tree','values':[]},
         {'__type':'graph','adjacency':[]}]
SIGNATURE = {'parameters':['linked_list','tree','graph'], 'returns':'int'}


class StructureTests(unittest.TestCase):
    def test_round_trip_preserves_sparse_tree_empty_values_and_cyclic_graph(self):
        for args in (ARGS, EMPTY):
            self.assertEqual(encode(decode(args),args),args)
        graph={'__type':'graph','adjacency':[[0,1],[0],[]]}
        self.assertEqual(encode(decode(graph),graph),graph)

    def test_invalid_shapes_cycles_orphans_and_sizes_are_rejected(self):
        invalid=[('tree',{'__type':'tree','values':[None,1]}),
                 ('tree',{'__type':'tree','values':[1,None]}),
                 ('graph',{'__type':'graph','adjacency':[[1]]}),
                 ('linked_list',{'__type':'linked_list','values':[True]}),
                 ('linked_list',{'__type':'linked_list','values':[0]*101})]
        for kind,value in invalid:
            with self.subTest(kind=kind),self.assertRaises(ValueError): typed_value(value,kind)
        node=decode(ARGS[0]); node.next=node
        with self.assertRaises(ValueError): encode(node,ARGS[0])
        root=decode(ARGS[1]); root.left=root
        with self.assertRaises(ValueError): encode(root,ARGS[1])


@unittest.skipUnless(os.environ.get('AM_STRUCTURE_TESTS')=='1','Set AM_STRUCTURE_TESTS=1 for real container checks.')
class StructureContainerTests(unittest.TestCase):
    def test_every_language_nonempty_empty_and_mutated_inputs(self):
        root=Path(__file__).resolve().parents[1]
        command=('docker',) if os.environ.get('AM_DOCKER_DIRECT')=='1' else ('sudo','-n','docker')
        image=(root/'.am-runtime/compiled-image.txt').read_text().strip()
        for language in ('python','c','cpp','java'):
            if language=='python':
                runner=DockerRunner((root/'infrastructure/python-runner-image.txt').read_text().strip(),command,wall_seconds=180)
                source='def solve(arg0,arg1,arg2):\n    total=len(arg2.adj)\n    while arg0:\n        total+=arg0.val\n        arg0=arg0.next\n    if arg1:\n        total+=arg1.val\n        if arg1.right: total+=arg1.right.val\n    return total\n'
                mutation=source.replace('    total=len(arg2.adj)','    arg2.adj[0].append(0)\n    total=len(arg2.adj)')
            else:
                runner=CompiledRunner(image,language,SIGNATURE,command,wall_seconds=180)
                arrow='.' if language=='java' else '->'
                size='arg2.adj.length' if language=='java' else '(int)arg2->adj.size()' if language=='cpp' else 'arg2->size'
                null='null' if language=='java' else 'NULL'
                pointer='ListNode' if language=='java' else 'const ListNode *'
                body=(f'int total={size}; for({pointer} p=arg0;p!={null};p=p{arrow}next) total+=p{arrow}val; '
                      f'if(arg1!={null}) {{ total+=arg1{arrow}val; if(arg1{arrow}right!={null}) total+=arg1{arrow}right{arrow}val; }} return total;')
                source=function_header(language,SIGNATURE)+' { '+body+' }'
                if language=='java': source='public class Solution { '+source+' }'
                mutate='arg2.adj[0][0]=0;' if language=='java' else 'const_cast<Graph*>(arg2)->adj[0][0]=0;' if language=='cpp' else '((Graph*)arg2)->adj[0][0]=0;'
                mutation=source.replace('int total=',mutate+' int total=')
            with self.subTest(language=language):
                for args, expected in ((ARGS,14),(EMPTY,0)):
                    result=grade_case(runner,source,'solve',{'name':'structure check','args':args,'expected':expected},True)
                    self.assertEqual(result['status'],'passed',result)
                result=grade_case(runner,mutation,'solve',{'name':'mutation check','args':ARGS,'expected':14},True)
                self.assertEqual(result['status'],'failed',result)
                self.assertTrue(result['input_modified'],result)
