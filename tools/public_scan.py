"""Conservative candidate-content check; NEVER copyright/privacy clearance."""
import hashlib
import json
from pathlib import Path
import re

if __package__:
    from . import provision
else:
    import provision

FORBIDDEN={'.git','.env','venv','snapshot','evidence','fixtures','cache','tmp','output','__pycache__','.pytest_cache','.runtime'}
SECRETS=re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|(?:sk-proj-)[A-Za-z0-9_-]{30,}')

def scan(root):
    root=Path(root)
    rows=[]
    for p in sorted(Path(root).rglob('*')):
        rel=p.relative_to(root)
        if p.is_symlink():raise ValueError('Symlink candidate: '+str(rel))
        if not p.is_file():continue
        if rel.parts[0]=='checker_engine':
            lock=json.loads((root/'upstream.lock.json').read_text())
            if rel!=Path('checker_engine')/(lock['commit']+'.tar.gz'):
                raise ValueError('Unexpected engine package file')
            files,bundle_sha=provision.bundled_source(root,lock)
            rows.append({'path':str(rel),'size':p.stat().st_size,'sha256':bundle_sha,
                'classification':'OWNER-AUTHORIZED LOCKED ENGINE RESOURCES','verified_files':len(files)})
            continue
        if any(x in FORBIDDEN for x in rel.parts) or p.suffix.lower() in ('.docx','.zip','.gz','.png','.jpg','.pyc','.pdf'):
            raise ValueError('Private/binary artifact in candidate: '+str(rel))
        raw=p.read_bytes()
        if SECRETS.search(raw):raise ValueError('Potential credential: '+str(rel))
        raw.decode('utf-8')
        rows.append({'path':str(rel),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'classification':'PROPOSED PUBLIC—OWNER RIGHTS REVIEW'})
    if not rows:raise ValueError('Empty public candidate')
    return rows

if __name__=='__main__':
    import sys
    print(json.dumps(scan(Path(sys.argv[1]).resolve()),indent=2))
