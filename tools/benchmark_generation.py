"""Measure live local generation/preparation; never substitute fixture results."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ai_exercises import OllamaExerciseGenerator, task_fingerprint
from am_core import AMError, PRACTICE_MODEL, api
from code_runner import DockerRunner, RunnerError
from compiled_runner import CompiledRunner
from note_retrieval import retrieve
from web_research import WebResearch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language',choices=['python','java','c','cpp'],default='python')
    parser.add_argument('--topic',required=True)
    parser.add_argument('--web-search',action='store_true',help='Retrieve documentation using language/topic only')
    parser.add_argument('--notes',type=Path,help='Optional UTF-8 notes file; stays local')
    parser.add_argument('--samples',type=int,default=3)
    parser.add_argument('--model',default=PRACTICE_MODEL)
    parser.add_argument('--review-model')
    parser.add_argument('--docker-direct',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/preparation-benchmark.json')
    args=parser.parse_args()
    if not 1<=args.samples<=20: parser.error('Choose 1 to 20 samples.')
    report={'report_type':'live-preparation-benchmark','timestamp_utc':datetime.now(timezone.utc).isoformat(),'language':args.language,
        'topic':args.topic,'model':args.model,'review_model':args.review_model or args.model,
        'requested':args.samples,'runs':[],'status':'running',
        'meaning':'Success means preparation passed review/execution checks, not universal correctness.'}
    result_code=0
    try:
        report['installed_model']=api('/api/show',{'model':args.model},timeout=5).get('details',{})
        notes=args.notes.read_text(encoding='utf-8') if args.notes else ''
        if len(notes)>200000: raise ValueError('Notes exceed 200,000 characters.')
        context,_=retrieve(args.topic,notes)
        research=WebResearch().gather(args.language,args.topic) if args.web_search else {'status':'disabled','sources':[]}
        report['web_research']={'status':research['status'],'urls':[row['url'] for row in research['sources']]}
        seen=set(); recent=[]
        command=('docker',) if args.docker_direct else ('sudo','-n','docker')
        runner=(DockerRunner((ROOT/'infrastructure/python-runner-image.txt').read_text().strip(),command)
                if args.language=='python' else CompiledRunner((ROOT/'.am-runtime/compiled-image.txt').read_text().strip(),args.language,command=command))
        for sample in range(args.samples):
            events=[]; generator=OllamaExerciseGenerator(runner,args.model,args.review_model,language=args.language,diagnostics=events.append)
            generator.research_sources=research['sources']; generator.seen_fingerprints=set(seen); generator.recent_tasks=list(recent)
            start=time.monotonic(); item={'sample':sample+1}
            try:
                lessons,_,_=generator.build(args.topic,context,'standard',1)
                item.update(success=True,combined_cases=len(lessons[0]['tests']),
                            reference_runs=lessons[0]['quality']['reference_runs'], verified_expectations=lessons[0]['quality']['review_test_repairs'],
                            starter_repairs=lessons[0]['quality'].get('starter_repairs',0))
                seen.add(task_fingerprint(lessons[0])); recent.append(lessons[0]['title'])
            except (AMError,OSError,ValueError,RunnerError,subprocess.SubprocessError) as error:
                item.update(success=False,error_type=type(error).__name__,error=str(error)[:500])
            item.update(seconds=round(time.monotonic()-start,3),rejections=dict(Counter(event['stage'] for event in events)),
                        last_response=generator.last_response_metadata)
            report['runs'].append(item)
            print(f"{sample+1}/{args.samples}: {'prepared' if item['success'] else 'failed'} in {item['seconds']} seconds",flush=True)
        report['status']='measured'
    except (AMError,OSError,ValueError,RunnerError,subprocess.SubprocessError) as error:
        report.update(status='unavailable',reason=str(error)[:500]); result_code=2
    except KeyboardInterrupt:
        report['status']='interrupted'; result_code=130
    runs=report['runs']; successes=sum(item['success'] for item in runs)
    report.update(attempted=len(runs),prepared=successes,preparation_rate=successes/len(runs) if runs else None,
                  median_seconds=statistics.median(item['seconds'] for item in runs) if runs else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Report: {args.output}; status={report['status']}; prepared={successes}/{len(runs)}")
    return result_code


if __name__=='__main__': raise SystemExit(main())
