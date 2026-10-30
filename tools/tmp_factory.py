"""Migration-only pytest directories accepted subprocess boundaries can write."""
from pathlib import Path
import tempfile

class LocalFactory:
    def __init__(self, root, parent):
        self.root=Path(root)/'tmp/pytest'
        self.root.mkdir(parents=True,exist_ok=True)
        # Pinned pytest uses the original retention policy during tmp_path teardown.
        self._retention_policy=parent._retention_policy
    def getbasetemp(self):
        return self.root
    def mktemp(self, basename, numbered=True):
        if Path(basename).name!=basename or basename in ('','.','..'):
            raise ValueError('Unsafe test directory name')
        if numbered:
            return Path(tempfile.mkdtemp(prefix=basename+'-',dir=self.root))
        target=self.root/basename
        target.mkdir()
        return target
