"""Build a fresh private runtime; upstream bytes never become public candidate files."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_members(raw, lock):
    wanted = {x['path']: x for x in lock['files']}
    found = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if not parts or '..' in parts or member.name.startswith('/'):
                raise ValueError('Unsafe archive member')
            if member.isdir():
                continue
            name = '/'.join(parts[1:])
            if not member.isfile() or name not in wanted or name in found:
                raise ValueError('Unexpected/linked/duplicate source member')
            data = archive.extractfile(member).read()
            blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if sha(data) != wanted[name]['sha256'] or blob != wanted[name]['git_blob']:
                raise ValueError('Pinned source bytes mismatch: '+name)
            found[name] = data
    if set(found) != set(wanted):
        raise ValueError('Incomplete pinned source')
    return found


def verify_candidate(root):
    for item in json.loads((root/'accepted.lock.json').read_text())['files']:
        if sha((root/item['path']).read_bytes()) != item['sha256']:
            raise ValueError('Accepted Checker identity mismatch: '+item['path'])


def create(destination):
    verify_candidate(ROOT)
    destination = Path(destination).absolute()
    # Never overwrite, follow links, or populate either ancestor or child of candidate.
    if destination.exists() or destination.is_symlink():
        raise ValueError('Runtime destination must be new')
    if destination.parent.resolve() != destination.parent:
        raise ValueError('Symlinked runtime parent')
    if destination.is_relative_to(ROOT) or ROOT.is_relative_to(destination):
        raise ValueError('Runtime must be separate from public candidate')
    if any((p/'.git').exists() for p in (destination.parent, *destination.parents)):
        raise ValueError('Runtime cannot be inside a Git worktree')
    lock = json.loads((ROOT/'upstream.lock.json').read_text())
    url = 'https://codeload.github.com/'+lock['repository']+'/tar.gz/'+lock['commit']
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read(32*1024*1024+1)
    if len(raw)>32*1024*1024:
        raise ValueError('Source archive too large')
    files = verify_members(raw, lock)
    destination.mkdir(mode=0o700)
    for directory, directories, names in os.walk(ROOT, followlinks=False):
        for name in directories+names:
            if (Path(directory)/name).is_symlink():
                raise ValueError('Candidate symlink prohibited')
        # A checkout's real Git directory/worktree marker is metadata, not input.
        directories[:]=[name for name in directories if name!='.git']
        for name in names:
            if name=='.git':
                continue
            source=Path(directory)/name
            relative=source.relative_to(ROOT)
            if any(x in ('.runtime','__pycache__','.pytest_cache') for x in relative.parts):
                raise ValueError('Private/generated candidate content')
            target=destination/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())
    for name, data in files.items():
        target = destination/'snapshot'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o444)
    inventory = ''.join(x['sha256']+'  snapshot/'+x['path']+'\n' for x in lock['files'])
    if sha(inventory.encode()) != lock['snapshot_manifest_sha256']:
        raise ValueError('Accepted inventory ordering mismatch')
    (destination/'evidence').mkdir()
    (destination/'evidence/snapshot.sha256').write_text(inventory)
    for group in ('', 'c02', 'c03', 'c04'):
        for folder in ('tmp','cache','fixtures','output','evidence'):
            (destination/group/folder).mkdir(parents=True, exist_ok=True)
    return {'runtime':str(destination), 'external_source_url':url,
            'archive_sha256':sha(raw),'verified_source_files':len(files),
            'source_commit':lock['commit'],'template_blob':lock['template_blob'],
            'public_source_redistribution':'NOT GRANTED; runtime only'}


def seed():
    """Fresh runtime equivalents, NOT historical RED or accepted fixture byte parity."""
    verify_candidate(ROOT)
    if not (ROOT/'snapshot/master_template.docx').is_file():
        raise ValueError('Provision pinned runtime first')
    sys.path[:0] = [str(ROOT),str(ROOT/'c02'),str(ROOT/'c03'),str(ROOT/'c04')]
    from test_c02 import operator as neat, fixture
    from test_c03 import operator as recipe
    from c03_source import request
    from c04_runtime import call
    op = neat()
    (ROOT/'c02/fixtures/operator-neat.json').write_text(json.dumps(op,indent=2))
    fixture(ROOT/'c02/fixtures/independent-neat-claims.docx')
    red = ROOT/'c03/fixtures/red-baseline-equivalent.docx'
    request({'action':'render_fixture','operator':op,'docx':str(red),
             'fixture':{'Main':{'dead':5,'tank':'Mud Reserve Tanks'}}})
    inspected = request({'action':'inspect','operator':op,'docx':str(red)})
    (ROOT/'c03/evidence/red-baseline.json').write_text(json.dumps(inspected))
    gross = recipe()
    gross['slurries']['Main']['additives']=[{'Material Type':'Custom Powder','Name':'C03 Powder',
        'Physical State':'Powder','Mix Method':'In Mix Water','User Input':1,'Density':1.4}]
    request({'action':'render_fixture','operator':gross,'docx':str(ROOT/'c03/fixtures/red-gross.docx'),
             'fixture':{'Main':{'dead':5,'tank':'Mud Reserve Tanks'}}})
    main = recipe(mixed=True)
    # C04's cross-boundary symlink control needs this C03 fixture even when
    # shard C runs on a different machine. Use the unchanged source renderer.
    request({'action':'render_fixture','operator':main,
             'docx':str(ROOT/'c03/fixtures/mixed5.docx'),
             'fixture':{'Main':{'dead':5,'tank':'Mud Reserve Tanks'}}})
    doc = ROOT/'c04/fixtures/synthetic-main.docx'
    result = call({'action':'fixture','operator':main,'docx':str(doc),
                   'fixture':{'Main':{'dead':5,'tank':'Mud Reserve Tanks'}}})
    (ROOT/'c04/fixtures/operator-main.json').write_text(json.dumps(main,indent=2))
    (ROOT/'c04/fixtures/synthetic-main-source.json').write_text(json.dumps(result))
    (ROOT/'c04/fixtures/edit-main.json').write_text('{"slurry":"Main","corrected_dead_volume_bbl":10}')
    baseline = call({'action':'baseline','operator':main,'docx':str(doc)})
    (ROOT/'c04/evidence/c03-baseline.json').write_text(json.dumps(baseline))
    assert baseline['status']=='PARTIAL_FINDINGS_ONLY'
    print(json.dumps({'generated':'fresh synthetic runtime equivalents','historical_red':False,
                      'private_original_fixtures_copied':False,'c03_status':baseline['status']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination')
    parser.add_argument('--seed',action='store_true')
    args=parser.parse_args()
    if args.seed:
        seed()
    elif args.destination:
        print(json.dumps(create(args.destination),indent=2))
    else:
        parser.error('Choose --destination NEW_DIRECTORY or --seed within provisioned runtime')
