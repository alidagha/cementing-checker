"""Same-process, request-authorized C10 delivery; never register DOCX media URLs."""
from functools import wraps
from hashlib import sha256
from html import escape
from ipaddress import ip_address
import re
import secrets
import threading
import time
from urllib.parse import parse_qs
import weakref

import streamlit as st
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import Route

COOKIE = 'checker_delivery_owner'
MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
TTL = 300
LIMIT = 32 * 1024 * 1024
HEADERS = {'Cache-Control':'no-store, private', 'Pragma':'no-cache',
    'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer'}
_registry = {}
_registry_lock = threading.RLock()
_ready = False


def locked(method):
    """Serialize receipt mutations with delivery authorization (reentrant)."""
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._delivery_lock:
            return method(self, *args, **kwargs)
    return call


def revoke(session):
    with _registry_lock:
        _registry.pop(getattr(session, '_download_grant', None), None)
        session._download_grant = None


def _cookie(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def issue(session, cookie, selected, confirmed):
    """Called only by the owning Streamlit session, using public context cookies."""
    with session._delivery_lock:
        if not _ready or not _cookie(cookie):
            revoke(session)
            raise ValueError('Use the documented delivery entrypoint')
        copy = session.current_created_copy(selected, confirmed)
        if copy is None or not 0 < len(copy['bytes']) <= LIMIT:
            revoke(session)
            raise ValueError('Current selected copy required')
        now = time.monotonic()
        with _registry_lock:
            for key, item in list(_registry.items()):
                if item['expires'] <= now or item['owner']() is None:
                    del _registry[key]
            key = getattr(session, '_download_grant', None)
            item = _registry.get(key)
            if (item is None or item['owner']() is not session or item['selected'] != tuple(selected)
                    or item['copy_id'] != copy['copy_id'] or item['cookie'] != sha256(cookie.encode()).digest()):
                revoke(session)
                if len(_registry) >= 128:  # ponytail: one process, bounded grants; no cross-worker registry.
                    raise ValueError('Delivery capacity unavailable')
                key = secrets.token_urlsafe(32)
                item = {'owner':weakref.ref(session), 'cookie':sha256(cookie.encode()).digest(),
                    'secret':secrets.token_urlsafe(32), 'selected':tuple(selected),
                    'copy_id':copy['copy_id'], 'sha':copy['receipt']['output_sha256'], 'expires':now + TTL}
                _registry[key] = item
                session._download_grant = key
            # Only generated ASCII credentials enter this static native form. No JS or untrusted HTML.
            return ('<form method="post" action="/c10-copy/' + escape(key, quote=True) + '">'
                '<input type="hidden" name="proof" value="' + escape(item['secret'], quote=True) + '">'
                '<button type="submit">Download selected-copy DOCX</button></form>')


def _denied():
    return Response('Copy unavailable', status_code=403, headers=HEADERS)


def _authorized_bytes(key, proof, cookie):
    if not _cookie(cookie): return None
    with _registry_lock:
        item = _registry.get(key)
    if item is None or not secrets.compare_digest(item['secret'], proof): return None
    owner = item['owner']()
    if owner is None: return None
    with owner._delivery_lock:
        with _registry_lock:
            if _registry.get(key) is not item: return None
        if (item['expires'] <= time.monotonic()
                or not secrets.compare_digest(item['cookie'], sha256(cookie.encode()).digest())):
            return None
        try:
            copy = owner.current_created_copy(list(item['selected']), True)
            if (copy is None or copy['copy_id'] != item['copy_id']
                    or copy['receipt']['output_sha256'] != item['sha']
                    or sha256(copy['bytes']).hexdigest() != item['sha']
                    or not 0 < len(copy['bytes']) <= LIMIT):
                revoke(owner)
                return None
            # Authorization linearizes here. A previously authorized in-flight response cannot be recalled.
            return copy['bytes']
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
            revoke(owner)
            return None


async def deliver(request):
    if (request.headers.get('origin') != str(request.base_url).rstrip('/')
            or request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded'
            or any(k in request.headers for k in ('range','if-none-match','if-modified-since'))):
        return _denied()
    raw = b''
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > 128: return _denied()
    try:
        fields = parse_qs(raw.decode('ascii'), strict_parsing=True, keep_blank_values=True)
        if set(fields) != {'proof'} or len(fields['proof']) != 1 or not re.fullmatch('[A-Za-z0-9_-]{43}', fields['proof'][0]):
            return _denied()
    except (ValueError, UnicodeError):
        return _denied()
    # Receipt verification is filesystem/CPU work; keep it off the ASGI event loop.
    from starlette.concurrency import run_in_threadpool
    data = await run_in_threadpool(_authorized_bytes, request.path_params['grant'], fields['proof'][0], request.cookies.get(COOKIE))
    if data is None: return _denied()
    return Response(data, media_type=MIME, headers=dict(HEADERS,
        **{'Content-Disposition':'attachment; filename="checker-selected-copy.docx"'}))


class DeliveryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        global _ready
        host = request.url.hostname or ''
        try: loopback = ip_address(host).is_loopback
        except ValueError: loopback = host == 'localhost'
        try: loopback = loopback and request.client is not None and ip_address(request.client.host).is_loopback
        except ValueError: loopback = False
        if request.url.scheme != 'https' and not loopback:
            return _denied()
        _ready = True
        response = await call_next(request)
        if request.url.path.startswith('/c10-copy/'):
            response.headers.update(HEADERS)
        # Defense against an old native-media registration in a warm process, independent of file suffix.
        if request.url.path.startswith('/media/') and response.headers.get('content-type','').split(';')[0] == MIME:
            return _denied()
        if request.url.path == '/' and not _cookie(request.cookies.get(COOKIE)):
            response.set_cookie(COOKIE, secrets.token_hex(32), httponly=True,
                secure=request.url.scheme == 'https', samesite='strict', path='/')
        return response


# Public supported startup: streamlit run c10_delivery.py. One process, no additional server.
app = st.App('checker_ui.py', routes=[Route('/c10-copy/{grant}', deliver, methods=['POST'])],
    middleware=[Middleware(DeliveryMiddleware)])
