"""Conservative candidate-content check; NEVER copyright/privacy clearance."""
import hashlib
import json
from pathlib import Path
import re

FORBIDDEN={'.git','.env','venv','snapshot','evidence','fixtures','cache','tmp','output','__pycache__','.pytest_cache','.runtime'}
SECRETS=re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|(?:sk-proj-)[A-Za-z0-9_-]{30,}')

def scan(root):
    rows=[]
    for p in sorted(Path(root).rglob('*')):
        rel=p.relative_to(root)
        if p.is_symlink():raise ValueError('Symlink candidate: '+str(rel))
        if not p.is_file():continue
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
