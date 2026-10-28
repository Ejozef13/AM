"""Reversibly archive the unused, untracked notes-study prototype. Dry run by default."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Move the recognized prototype into .am-archive; never delete it')
    args = parser.parse_args()
    bootstrap = ROOT/'study_app.py'
    if not bootstrap.is_file() or 'from study.providers import' not in bootstrap.read_text():
        print('No recognized legacy study prototype to archive.')
        return
    paths = [path for path in (bootstrap,ROOT/'study') if path.exists()]
    result = subprocess.run(['git','ls-files','--',*[path.name for path in paths]],
                            cwd=ROOT,check=True,capture_output=True,text=True)
    if result.stdout.strip():
        raise SystemExit('These prototype paths contain tracked files; no files were moved.')
    if not args.apply:
        print('Would archive: '+', '.join(path.name for path in paths)+'. Run with --apply to move them.')
        return
    target = ROOT/'.am-archive'/('legacy-study-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    target.mkdir(parents=True,mode=0o700)
    for path in paths:
        path.rename(target/path.name)
    print('Archived the unused prototype, without deleting it: '+str(target))


if __name__ == '__main__':
    main()
