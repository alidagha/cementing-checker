"""Private file primitives; Windows requires owner-only NTFS handles, never a fallback."""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path


class UnsupportedSecurity(OSError):
    def __init__(self):
        super().__init__('UNSUPPORTED_WINDOWS_SECURITY')


def _windows():
    if os.name != 'nt':
        raise UnsupportedSecurity()
    return _Windows()


def _filename(path):
    name=Path(path).name
    reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if (not name or ':' in name or name.endswith((' ','.')) or '\x00' in name
            or name.split('.')[0].upper() in reserved):raise UnsupportedSecurity()
    return name


class _Windows:
    """Documented Win32 handle operations; sharing denies writes/deletion while pinned."""
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c, w
        self.k = c.WinDLL('kernel32', use_last_error=True)
        self.a = c.WinDLL('advapi32', use_last_error=True)
        class Info(c.Structure):
            _fields_ = [('attributes',w.DWORD),('created',w.FILETIME),('accessed',w.FILETIME),
                ('written',w.FILETIME),('volume',w.DWORD),('size_high',w.DWORD),('size_low',w.DWORD),
                ('links',w.DWORD),('index_high',w.DWORD),('index_low',w.DWORD)]
        self.Info=Info
        signatures = {
            'CreateFileW':([w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE),
            'GetDriveTypeW':([w.LPCWSTR],w.UINT),
            'CloseHandle':([w.HANDLE],w.BOOL),
            'GetFileInformationByHandle':([w.HANDLE,c.POINTER(Info)],w.BOOL),
            'GetVolumeInformationByHandleW':([w.HANDLE,w.LPWSTR,w.DWORD,c.POINTER(w.DWORD),c.POINTER(w.DWORD),c.POINTER(w.DWORD),w.LPWSTR,w.DWORD],w.BOOL),
            'SetFileInformationByHandle':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL),
            'LocalFree':([c.c_void_p],c.c_void_p),
            'GetCurrentProcess':([],w.HANDLE)}
        for name,(args,result) in signatures.items():
            f=getattr(self.k,name);f.argtypes=args;f.restype=result
        for name,args,result in [
            ('OpenProcessToken',[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],w.BOOL),
            ('GetTokenInformation',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)],w.BOOL),
            ('ConvertSidToStringSidW',[c.c_void_p,c.POINTER(w.LPWSTR)],w.BOOL),
            ('ConvertStringSecurityDescriptorToSecurityDescriptorW',[w.LPCWSTR,w.DWORD,c.POINTER(c.c_void_p),c.POINTER(w.DWORD)],w.BOOL),
            ('GetSecurityInfo',[w.HANDLE,c.c_int,w.DWORD,c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p)],w.DWORD),
            ('GetAce',[c.c_void_p,w.DWORD,c.POINTER(c.c_void_p)],w.BOOL),
            ('EqualSid',[c.c_void_p,c.c_void_p],w.BOOL)]:
            f=getattr(self.a,name);f.argtypes=args;f.restype=result
        token=w.HANDLE();self.check(self.a.OpenProcessToken(self.k.GetCurrentProcess(),8,c.byref(token)))
        try:
            size=w.DWORD();self.a.GetTokenInformation(token,1,None,0,c.byref(size))
            self.token=c.create_string_buffer(size.value)
            self.check(self.a.GetTokenInformation(token,1,self.token,size,c.byref(size)))
            self.sid=c.c_void_p.from_buffer(self.token).value
            sid_text=w.LPWSTR();self.check(self.a.ConvertSidToStringSidW(self.sid,c.byref(sid_text)))
            try:self.sid_text=sid_text.value
            finally:self.k.LocalFree(c.cast(sid_text,c.c_void_p))
        finally:self.k.CloseHandle(token)

    def check(self,value):
        if not value:raise UnsupportedSecurity()
        return value

    def close(self,handle):
        self.check(self.k.CloseHandle(handle))

    def open(self,path,directory=False,create=False,publication=False):
        c,w=self.c,self.w
        if not directory:_filename(path)
        descriptor=c.c_void_p()
        class Attributes(c.Structure):
            _fields_=[('size',w.DWORD),('descriptor',c.c_void_p),('inherit',w.BOOL)]
        attributes=None
        if create:
            # Protected DACL: current account only, inherited by runtime descendants.
            sddl='O:'+self.sid_text+'D:P(A;OICI;FA;;;'+self.sid_text+')'
            self.check(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,c.byref(descriptor),None))
            attributes=Attributes(c.sizeof(Attributes),descriptor,False)
        try:
            access=0x20000|0x80  # READ_CONTROL, FILE_READ_ATTRIBUTES
            if create:access|=0xC0000000  # GENERIC_READ/WRITE; CRT readers need not share DELETE
            if publication:access|=0x80010000  # GENERIC_READ and DELETE, after all child rechecks
            flags=0x00200000|(0x02000000 if directory else 0)  # OPEN_REPARSE_POINT, BACKUP_SEMANTICS
            h=self.k.CreateFileW('\\\\?\\'+str(path),access,1,c.byref(attributes) if attributes else None,1 if create else 3,flags,None)
            if h==c.c_void_p(-1).value:
                if create and c.get_last_error() in (80,183):raise FileExistsError('PRIVATE_OUTPUT_COLLISION')
                raise UnsupportedSecurity()
        finally:
            if descriptor:self.k.LocalFree(descriptor)
        try:
            info=self.Info();self.check(self.k.GetFileInformationByHandle(h,c.byref(info)))
            if info.attributes&0x400 or bool(info.attributes&0x10)!=directory or not directory and info.links!=1:
                raise UnsupportedSecurity()
            return h
        except BaseException:
            self.k.CloseHandle(h);raise

    def owner_only(self,handle):
        c,w=self.c,self.w;owner=c.c_void_p();acl=c.c_void_p();descriptor=c.c_void_p()
        class ACL(c.Structure):
            _fields_=[('revision',c.c_ubyte),('reserved',c.c_ubyte),('size',w.WORD),('count',w.WORD),('reserved2',w.WORD)]
        try:
            if self.a.GetSecurityInfo(handle,1,5,c.byref(owner),None,c.byref(acl),None,c.byref(descriptor))!=0:
                raise UnsupportedSecurity()
            if not owner or not acl or not self.a.EqualSid(owner,self.sid):raise UnsupportedSecurity()
            count=c.cast(acl,c.POINTER(ACL)).contents.count
            if not count:raise UnsupportedSecurity()
            for index in range(count):
                ace=c.c_void_p();self.check(self.a.GetAce(acl,index,c.byref(ace)))
                # ACCESS_ALLOWED_ACE has SID at offset 8; no broad/group/callback ACE is accepted.
                if c.c_ubyte.from_address(ace.value).value!=0 or not self.a.EqualSid(ace.value+8,self.sid):
                    raise UnsupportedSecurity()
        finally:
            if descriptor:self.k.LocalFree(descriptor)

    def local_volume(self,path):
        path=Path(path)
        if (not path.is_absolute() or len(path.anchor)!=3 or path.anchor[1:]!=':\\'
                or self.k.GetDriveTypeW(path.anchor) not in (2,3)):
            raise UnsupportedSecurity()

    @contextmanager
    def parents(self,path):
        path=Path(path)
        # Local NTFS only; reject UNC/device/drive-relative forms and reparse components.
        if (not path.is_absolute() or len(path.anchor)!=3 or path.anchor[1:]!=':\\'
                or any(part in ('.','..') or ':' in part or part.endswith((' ','.')) for part in path.parts[1:])):
            raise UnsupportedSecurity()
        self.local_volume(path)
        with ExitStack() as stack:
            current=Path(path.anchor);h=self.open(current,True);stack.callback(self.close,h)
            fs=self.c.create_unicode_buffer(32)
            self.check(self.k.GetVolumeInformationByHandleW(h,None,0,None,None,None,fs,32))
            if fs.value!='NTFS':raise UnsupportedSecurity()
            for part in path.parts[1:]:
                current=current/part;h=self.open(current,True);stack.callback(self.close,h)
            yield h

    @contextmanager
    def pinned(self,path):
        path=Path(path)
        with self.parents(path.parent):
            h=self.open(path)
            try:
                self.owner_only(h);yield h
            finally:self.close(h)

    def identity(self,handle):
        value=self.Info();self.check(self.k.GetFileInformationByHandle(handle,self.c.byref(value)))
        return (value.volume,value.index_high,value.index_low)

    def read(self,handle):
        c,w=self.c,self.w
        f=self.k.ReadFile;f.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p];f.restype=w.BOOL
        chunks=[];size=0
        while True:
            block=c.create_string_buffer(65536);count=w.DWORD();self.check(f(handle,block,65536,c.byref(count),None))
            if not count.value:break
            size+=count.value
            if size>32*1024*1024:raise UnsupportedSecurity()
            chunks.append(block.raw[:count.value])
        return b''.join(chunks)

    def dispose(self,handle):
        value=self.w.BOOL(True)
        self.check(self.k.SetFileInformationByHandle(handle,4,self.c.byref(value),self.c.sizeof(value)))

    def publish(self,handle,path):
        _filename(path)
        c=self.c;encoded=str(path).encode('utf-16-le')
        class Rename(c.Structure):
            _fields_=[('replace',c.c_ubyte),('root',c.c_void_p),('length',c.c_uint32),('name',c.c_uint16*((len(encoded)//2)+1))]
        value=Rename();value.replace=False;value.root=None;value.length=len(encoded)
        c.memmove(c.addressof(value)+Rename.name.offset,encoded,len(encoded))
        # Kernel-enforced no-replace, using the actual still-open staging file handle.
        if not self.k.SetFileInformationByHandle(handle,3,c.byref(value),c.sizeof(value)):
            if c.get_last_error() in (80,183):raise FileExistsError('PRIVATE_OUTPUT_COLLISION')
            raise UnsupportedSecurity()


def private_permissions(path):
    path=Path(path)
    if os.name!='nt':return not bool(path.stat().st_mode&0o077)
    try:
        w=_windows()
        if path.is_dir():
            with w.parents(path) as h:w.owner_only(h)
        else:
            with w.pinned(path):pass
        return True
    except OSError:return False


def exclusive_create(path):
    if os.name!='nt':return os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    import msvcrt
    w=_windows();path=Path(path)
    with w.parents(path.parent) as parent:
        w.owner_only(parent);h=w.open(path,create=True)
        try:w.owner_only(h);return msvcrt.open_osfhandle(h,os.O_WRONLY|os.O_BINARY)
        except BaseException:w.close(h);raise


@contextmanager
def windows_transaction(parent,inputs):
    """Pin every ancestor and input until publication/cleanup completes."""
    w=_windows();parent=Path(parent)
    with ExitStack() as stack:
        h=stack.enter_context(w.parents(parent));w.owner_only(h)
        for path in inputs:stack.enter_context(w.pinned(Path(path)))
        yield w


@contextmanager
def windows_stage(w,path,data):
    import msvcrt
    h=w.open(path,create=True);identity=w.identity(h);fd=None;published=False
    try:
        w.owner_only(h);fd=msvcrt.open_osfhandle(h,os.O_RDWR|os.O_BINARY)
        with os.fdopen(fd,'w+b',closefd=False) as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        # Readers in unchanged Python workers do not share DELETE. Close the
        # writer before child rechecks; reacquire and prove the exact inode/bytes
        # under a non-sharing DELETE handle immediately before publication.
        os.close(fd);fd=None;h=None
        def publish(destination):
            nonlocal published
            handle=w.open(path,publication=True)
            try:
                w.owner_only(handle)
                if w.identity(handle)!=identity or w.read(handle)!=data:raise UnsupportedSecurity()
                w.publish(handle,destination);published=True
            finally:w.close(handle)
        yield publish
    finally:
        if fd is not None:os.close(fd);h=None
        elif h is not None:w.close(h)
        if not published:
            handle=w.open(path,publication=True)
            try:
                if w.identity(handle)!=identity:raise UnsupportedSecurity()
                w.dispose(handle)
            finally:w.close(handle)


def create_private_directory(path):
    path=Path(path)
    if os.name!='nt':path.mkdir(mode=0o700);return
    w=_windows();c=w.c
    class Attributes(c.Structure):
        _fields_=[('size',w.w.DWORD),('descriptor',c.c_void_p),('inherit',w.w.BOOL)]
    descriptor=c.c_void_p()
    w.check(w.a.ConvertStringSecurityDescriptorToSecurityDescriptorW('O:'+w.sid_text+'D:P(A;OICI;FA;;;'+w.sid_text+')',1,c.byref(descriptor),None))
    try:
        attributes=Attributes(c.sizeof(Attributes),descriptor,False)
        f=w.k.CreateDirectoryW;f.argtypes=[w.w.LPCWSTR,c.c_void_p];f.restype=w.w.BOOL
        with w.parents(path.parent):w.check(f(str(path),c.byref(attributes)))
        if not private_permissions(path):raise UnsupportedSecurity()
    finally:w.k.LocalFree(descriptor)
