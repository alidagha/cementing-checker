"""Actual C10 receipt checks plus bounded ASGI delivery negatives; browser proof separate."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import re
from urllib.parse import urlencode

import pytest
from starlette.requests import Request
import c10_delivery as d
from test_g08a6_c10_ui import copy_control, proof, checked, ids, retain_copy


def grant(s, proof, monkeypatch):
    monkeypatch.setattr(d, '_ready', True)
    retain_copy(s, proof['copies']['yield'])
    form = d.issue(s, 'a'*64, ids(proof, 'yield'), True)
    key = re.search('/c10-copy/([^\"]+)', form)[1]
    secret = re.search('name="proof" value="([^\"]+)', form)[1]
    return key, secret


def response(key, secret, cookie='a'*64, headers=None, body=None):
    raw = urlencode({'proof':secret}).encode() if body is None else body
    h = {'origin':'http://localhost', 'host':'localhost', 'content-type':'application/x-www-form-urlencoded',
        'cookie':d.COOKIE+'='+cookie}
    h.update(headers or {})
    scope = {'type':'http', 'method':'POST', 'scheme':'http', 'path':'/c10-copy/'+key,
        'root_path':'', 'query_string':b'', 'server':('localhost',80),
        'headers':[(k.encode(),v.encode()) for k,v in h.items()], 'path_params':{'grant':key}}
    async def receive(): return {'type':'http.request','body':raw,'more_body':False}
    return asyncio.run(d.deliver(Request(scope, receive)))


def test_real_C10_receipt_delivers_only_to_cookie_and_session_proof(checked, proof, monkeypatch):
    s, path, before = checked; original = path.read_bytes()
    key, secret = grant(s, proof, monkeypatch)
    r = response(key, secret)
    assert r.status_code == 200 and r.body == proof['copies']['yield']['bytes']
    assert r.headers['cache-control'] == 'no-store, private'
    assert r.headers['content-type'] == d.MIME and 'attachment;' in r.headers['content-disposition']
    for cookie, token in (('b'*64,secret),('',secret),('a'*64,'b'*43)):
        refused = response(key, token, cookie)
        assert refused.status_code == 403 and refused.body != r.body
    assert response(key, secret).body == r.body  # unchanged authorized benign rerun/replay
    assert s.current() == before and path.read_bytes() == original


def test_selection_consent_and_revision_revoke_existing_HTTP_delivery(checked, proof, monkeypatch):
    s, path, before = checked
    for mutation in ('selection','consent','revision','inspection'):
        s.result=deepcopy(before); s.document=path; s.revision=before['receipt']['revision']
        s.copy_proposal=deepcopy(proof['inspection'])
        key, secret = grant(s, proof, monkeypatch)
        assert response(key, secret).status_code == 200
        if mutation == 'selection': assert s.current_created_copy(ids(proof,'sacks'),True) is None
        elif mutation == 'consent':
            with pytest.raises(ValueError): s.current_created_copy(ids(proof,'yield'),False)
        elif mutation == 'revision': s.invalidate('independent-input-changed')
        else: s._clear_copy()
        assert response(key, secret).status_code == 403
        assert key not in d._registry


def test_current_source_copy_and_owner_identity_are_checked_at_transfer(checked, proof, monkeypatch):
    s, path, before = checked
    for kind in ('copy-bytes','copy-receipt','report','document','source','expired'):
        s.result=deepcopy(before); s.document=path; s.revision=before['receipt']['revision']
        s.copy_proposal=deepcopy(proof['inspection'])
        key, secret = grant(s, proof, monkeypatch)
        with monkeypatch.context() as m:
            if kind=='copy-bytes': s.copy_output['bytes'] += b'forged'
            elif kind=='copy-receipt': s.copy_output['receipt']['request']['session_id']='foreign'
            elif kind=='report': s.result['receipt']['session_id']='foreign'
            elif kind=='document': s.document=path.parent/'missing.docx'
            elif kind=='source':
                import g07_report as g
                m.setattr(g, 'identities', lambda: {})
            else: d._registry[key]['expires']=0
            refused=response(key,secret)
            assert refused.status_code==403 and refused.body!=proof['copies']['yield']['bytes']


def test_request_shape_origin_range_and_size_fail_closed(checked, proof, monkeypatch):
    s, _, _ = checked; key, secret=grant(s,proof,monkeypatch)
    for headers,body in (({'origin':'http://foreign'},None),({'origin':''},None),
            ({'content-type':'application/json'},None),({'range':'bytes=0-5'},None),
            ({'if-none-match':'anything'},None),({},b'x'*129),({},b'proof=x&proof=y'),
            ({},b'proof='+secret.encode()+b'&extra=x'),({},b'proof='+secret.encode()+b'&extra='),
            ({},b'proof='+secret.encode()+b'&proof='),({},b'proof=%ff')):
        assert response(key,secret,headers=headers,body=body).status_code==403
    assert response('../unknown',secret).status_code==403


def test_revoked_grant_cannot_resurrect_during_concurrent_requests(checked, proof, monkeypatch):
    s, _, _=checked; key,secret=grant(s,proof,monkeypatch)
    with s._delivery_lock:
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Reentrant revocation completes before either delivery can authorize.
            d.revoke(s)
            futures=[pool.submit(d._authorized_bytes,key,secret,'a'*64) for _ in range(2)]
        assert all(f.result() is None for f in futures)


def test_legacy_entrypoint_and_invalid_gating_never_issue_delivery(checked, proof, monkeypatch):
    s, _, _=checked
    monkeypatch.setattr(d,'_ready',False)
    with pytest.raises(ValueError): d.issue(s,'a'*64,ids(proof,'yield'),True)
    monkeypatch.setattr(d,'_ready',True)
    for cookie,selection,consent in (('invalid',ids(proof,'yield'),True),('a'*64,[],True),
            ('a'*64,ids(proof,'yield'),False),('a'*64,ids(proof,'yield')*2,True)):
        with pytest.raises(ValueError): d.issue(s,cookie,selection,consent)
        assert getattr(s,'_download_grant',None) is None


def test_failed_recreation_revokes_previous_transport_before_C10_call(checked, proof, monkeypatch):
    import subprocess
    import c10_corrections as c
    s, path, before=checked; key,secret=grant(s,proof,monkeypatch)
    def timeout(*args): raise subprocess.TimeoutExpired('private-worker',120)
    monkeypatch.setattr(c,'apply',timeout)
    with pytest.raises(ValueError,match='SOURCE_UNAVAILABLE'): s.create_selected_copy(ids(proof,'yield'),True)
    assert response(key,secret).status_code==403 and s.current()==before


def test_middleware_blocks_warm_DOCX_media_and_unsafe_transport_and_sets_cookie():
    from starlette.responses import Response
    async def run(path='/',scheme='http',host='localhost',client='127.0.0.1',mime='text/html'):
        request=Request({'type':'http','method':'GET','scheme':scheme,'path':path,'root_path':'',
            'query_string':b'','client':(client,12345),'server':(host,80),'headers':[(b'host',host.encode())]})
        async def next_call(request):return Response(b'probe',media_type=mime)
        return await d.DeliveryMiddleware(None).dispatch(request,next_call)
    normal=asyncio.run(run())
    assert normal.status_code==200 and 'HttpOnly' in normal.headers['set-cookie'] and 'SameSite=strict' in normal.headers['set-cookie']
    tls=asyncio.run(run(scheme='https'))
    assert 'Secure' in tls.headers['set-cookie']
    assert asyncio.run(run(host='external.invalid',client='192.0.2.1')).status_code==403
    assert asyncio.run(run(host='localhost',client='192.0.2.1')).status_code==403
    assert asyncio.run(run(path='/media/old-file',mime=d.MIME)).status_code==403
