"""Opt-in, bounded diagnostic metadata; never native certification evidence."""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

LIMIT = 4 * 1024 * 1024
MAX_EVENTS = 8192
HEX = re.compile(r'[0-9a-f]{64}')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


class Journal:
    def __init__(self, path, identity):
        self.path = Path(path)
        self.identity = identity
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.seq = self.size = 0
        self.previous = '0' * 64
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.event('binding', identity=identity, schema='checker-diagnostic.1')

    def event(self, kind, **fields):
        with self.lock:
            record = dict(seq=self.seq, elapsed=round(time.monotonic()-self.started, 6),
                          kind=kind, previous=self.previous, **fields)
            record['sha256'] = hashlib.sha256(encoded(record)).hexdigest()
            raw = encoded(record) + b'\n'
            if self.seq >= MAX_EVENTS or self.size + len(raw) > LIMIT:
                raise ValueError('Diagnostic metadata limit')
            if os.write(self.fd, raw) != len(raw):
                raise OSError('Incomplete diagnostic write')
            os.fsync(self.fd)
            self.seq += 1
            self.size += len(raw)
            self.previous = record['sha256']

    def phase(self, ordinal, nodeid, phase, edge):
        # Hash the full native identity; never persist parametrized IDs.
        module = nodeid.split('::', 1)[0]
        if not re.fullmatch(r'(?:[a-z0-9_]+/)*test_[a-z0-9_]+\.py', module):
            raise ValueError('Non-allowlisted diagnostic module')
        self.event('phase', ordinal=ordinal, node=hashlib.sha256(nodeid.encode()).hexdigest(),
                   module=module, phase=phase, edge=edge)

    def close(self):
        os.close(self.fd)


def read_journal(path, identity):
    """Refuse missing, malformed, cross-run or altered diagnostic records."""
    path = Path(path)
    if path.is_symlink() or not 0 < path.stat().st_size <= LIMIT:
        raise ValueError('Invalid diagnostic file')
    records = []
    previous = '0' * 64
    elapsed = -1
    allowed = {
        'binding': {'identity', 'schema'},
        'phase': {'ordinal', 'node', 'module', 'phase', 'edge'},
        'collection': {'edge'},
        'resources': {'available', 'processes', 'started', 'exited', 'cpu_ticks',
                      'rss_bytes', 'read_bytes', 'write_bytes'},
        'observer_stop': set(),
    }
    for line in path.read_bytes().splitlines():
        r = json.loads(line)
        checksum = r.pop('sha256')
        if (r.get('kind') not in allowed or
                set(r) != {'seq', 'elapsed', 'kind', 'previous'} | allowed[r['kind']] or
                r['seq'] != len(records) or r['previous'] != previous or
                type(r['elapsed']) not in (int, float) or not elapsed <= r['elapsed'] < 86400 or
                hashlib.sha256(encoded(r)).hexdigest() != checksum):
            raise ValueError('Diagnostic chain/schema mismatch')
        if r['kind'] == 'binding':
            if records or r['identity'] != identity or r['schema'] != 'checker-diagnostic.1':
                raise ValueError('Diagnostic identity mismatch')
        elif not records:
            raise ValueError('Missing diagnostic binding')
        if r['kind'] == 'phase':
            if (type(r['ordinal']) is not int or r['ordinal'] < 1 or
                    not HEX.fullmatch(r['node']) or
                    not re.fullmatch(r'(?:[a-z0-9_]+/)*test_[a-z0-9_]+\.py', r['module']) or
                    r['phase'] not in ('setup', 'call', 'teardown') or r['edge'] not in ('start', 'finish')):
                raise ValueError('Invalid diagnostic phase')
        if r['kind'] == 'collection' and r['edge'] not in ('start', 'finish'):
            raise ValueError('Invalid diagnostic collection')
        if r['kind'] == 'resources':
            if (type(r['available']) is not bool or any(type(r[k]) is not int or r[k] < 0
                    for k in allowed['resources']-{'available'})):
                raise ValueError('Invalid diagnostic counters')
        previous, elapsed = checksum, r['elapsed']
        records.append(dict(r, sha256=checksum))
        if len(records) > MAX_EVENTS:
            raise ValueError('Diagnostic event limit')
    if not records:
        raise ValueError('Missing diagnostic records')
    return records


class Observer:
    """Sample only descendant aggregate counters, never argv, environment or paths."""
    def __init__(self, journal):
        self.journal = journal
        self.root = os.getpid()
        self.stop = threading.Event()
        self.seen = {}
        self.previous = set()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def sample(self):
        table = {}
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
                table[int(entry.name)] = (int(fields[1]), int(fields[19]),
                    int(fields[11])+int(fields[12]), int(fields[21])*os.sysconf('SC_PAGE_SIZE'))
            except (OSError, ValueError, IndexError):
                continue
        owned = {self.root}
        while True:
            found = {p for p, data in table.items() if data[0] in owned}
            if found <= owned:
                break
            owned |= found
        current = set()
        rss = 0
        for pid in owned & table.keys():
            _, start, cpu, memory = table[pid]
            key = (pid, start)
            current.add(key)
            rss += memory
            counters = {}
            try:
                counters = dict(line.split(': ', 1) for line in (Path('/proc')/str(pid)/'io').read_text().splitlines())
            except OSError:
                pass
            self.seen[key] = (cpu, int(counters.get('read_bytes', 0)), int(counters.get('write_bytes', 0)))
        sums = [sum(v[i] for v in self.seen.values()) for i in range(3)]
        self.journal.event('resources', available=self.root in table, processes=len(current),
            started=len(current-self.previous), exited=len(self.previous-current),
            cpu_ticks=sums[0], rss_bytes=rss, read_bytes=sums[1], write_bytes=sums[2])
        self.previous = current

    def run(self):
        while not self.stop.is_set():
            self.sample()
            self.stop.wait(5)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            raise RuntimeError('Diagnostic observer did not stop')
        self.journal.event('observer_stop')
        self.journal.close()
