"""Additive C03 interpretation; all accepted C02 findings remain unchanged."""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal
import json
import hashlib
import math
from pathlib import Path
import re
import sys

from c03_source import request,HERE,PIN

NOTE=re.compile(r'^NOTE (?P<note>\d+): Mix above Additives in (?P<water>.*?) Fresh Water at (?P<tank>.+)\.$')
SUFFIXES=('Cement Slurry Data','Cement Slurry Blend Data','Cement Slurry Additives Data')


def total_token(segment):
    pieces=segment.rsplit(maxsplit=1)
    raw,unit=pieces if len(pieces)==2 else ('',pieces[0] if pieces else '')
    if not raw:state='MISSING'
    elif raw in ('-','–','—'):state='DASH'
    elif raw.casefold() in ('n/a','not applicable'):state='NA_PRINTED'
    elif not re.fullmatch(r'[+-]?\d+\.\d',raw):state='MALFORMED_OR_UNPROVEN_PRECISION'
    else:state='ZERO' if Decimal(raw)==0 else 'NEGATIVE' if Decimal(raw)<0 else 'NUMBER'
    return raw,unit,state


def infer(raw,pure):
    """Authorized subtraction + conservative enclosure, never a tank-heel rule."""
    total=Decimal(raw);base=Decimal(str(pure));nominal=total-base
    lower=total-Decimal('.05')-base;upper=total+Decimal('.05')-base
    result={'nominal_bbl':str(nominal),'source_full_precision_pure_bbl':pure,
        'compatible_display_dv_interval_bbl':{'lower':str(lower),'upper':str(upper),
            'lower_inclusive':total>0,'upper_inclusive':total<0},
        'nominal_source_valid':nominal>=0,'not_a_measured_heel':True,'samples':None}
    if total<0 or upper<=0:
        result['qualification']='INCONSISTENT_WITH_SOURCE_NONNEGATIVE_ALLOWANCE'
        return result
    # This is an explicit intersection with the EXISTING App input domain,
    # never replacement/clamping of the (retained, possibly negative) nominal.
    feasible_lower=max(Decimal(0),lower)
    result['source_feasible_interval_bbl']={'lower':str(feasible_lower),'upper':str(upper),
        'reason':'Intersection with original validate_cement_parameters dead_vol >= 0'}
    # Outward adjacent floats conservatively include endpoint conversion and
    # source double arithmetic. Closed bounds can overestimate uncertainty.
    arithmetic_pad=2*max(math.ulp(float(total)),math.ulp(pure),math.ulp(float(upper)))
    result['source_float_enclosure_padding_bbl']=arithmetic_pad
    low=max(0.0,math.nextafter(float(feasible_lower)-arithmetic_pad,-math.inf))
    high=math.nextafter(float(upper)+arithmetic_pad,math.inf)
    samples={'lower_enclosure':low,'upper_enclosure':high}
    if nominal>=0:samples['nominal']=float(nominal)
    if not all(math.isfinite(x) for x in samples.values()):raise ValueError('Nonfinite inference enclosure')
    result.update(samples=samples,qualification='INFERRED_AT_DISPLAY_PRECISION')
    return result


def attributed_groups(records,active):
    blocks=defaultdict(list)
    for r in records:blocks[r['locator']['body_block']].append(r)
    groups=defaultdict(list);unassigned=[];current=None;phase=0
    for _,rows in sorted(blocks.items()):
        first=rows[0]
        if first['section']!='cement':current=None;phase=0;continue
        if first['locator'].get('table') is not None:
            fluid=first['association'];anchor=first['table_anchor']
            proof=fluid in active and all(r['association']==fluid and r['association_state']=='EXPLICIT' for r in rows)
            if proof and anchor==fluid+' '+SUFFIXES[0]:
                current={'fluid':fluid,'table_locators':[first['locator']],'notes':[],'complete':False}
                groups[fluid].append(current);phase=1
            elif proof and current and fluid==current['fluid'] and phase in (1,2) and anchor==fluid+' '+SUFFIXES[phase]:
                current['table_locators'].append(first['locator']);phase+=1;current['complete']=phase==3
            else:current=None;phase=0
            continue
        for r in rows:
            text=' '.join(r['raw_text'].split())
            if not text:continue
            if 'Mix above Additives in' in text:
                if current and current['complete']:current['notes'].append(r)
                else:unassigned.append(r)
            else:current=None;phase=0
    return groups,unassigned


def procedure_crosschecks(records,active):
    out=[]
    for r in records:
        if r['section']!='procedure':continue
        text=' '.join(r['raw_text'].split())
        m=re.fullmatch(r'\d+\. Fill up (.+) with Fresh water \((.+)\) for mixing fluids\.',text)
        if not m:m=re.fullmatch(r'\d+\. Fill up (.+) with (.+) fresh water for mixing fluid\.',text)
        if not m:continue
        tank,parts=m.groups();named=None
        if len(active)==1:
            fluid=next(iter(active));named=re.fullmatch(re.escape(fluid)+r': ([+-]?\d+\.\d) bbl',parts)
        out.append({'record':r,'tank':tank,'total':named[1] if named else None,
                    'fluid':next(iter(active)) if named else None,
                    'result':'NOT_VERIFIABLE','reason':'Procedure alone is not individual tank/water proof; aggregates never allocated'})
    return out


def analyze(path,operator):
    inspected=request({'action':'inspect','operator':operator,'docx':str(Path(path).resolve())})
    return extend(inspected,operator)


def extend(inspected,operator):
    if inspected.get('source_sha')!=PIN:raise ValueError('Source SHA drift')
    baseline=inspected['c02'];parsed=inspected['parsed'];ref=baseline['reference']
    if ref['source_sha']!=PIN or parsed['source_document_sha256']!=baseline['source_document_sha256']:
        raise ValueError('Reference/document provenance mismatch')
    if ref['operator_input_sha256']!=hashlib.sha256(json.dumps(operator,sort_keys=True,allow_nan=False).encode()).hexdigest():
        raise ValueError('Independent operator/reference identity mismatch')
    active={f for f,s in ref['slurries'].items() if s['program_section']=='cement'}
    groups,unassigned=attributed_groups(parsed['records'],active)
    procedures=procedure_crosschecks(parsed['records'],active)
    note_counts=Counter(r['note'] for r in parsed['records'] if 'Mix above Additives in' in r['raw_text'] and r['section']=='cement')
    water=[];allowances={}
    for fluid,s in ref['slurries'].items():
        f={'slurry':fluid,'status':'NOT_VERIFIABLE','source_sha':PIN,
           'source_document_sha256':parsed['source_document_sha256'],
           'Pure Mix Water Required':{'full_precision_bbl':s['calc']['field_water_bbl'],
                'source_display_bbl':s['display']['mix_water_bbl'],
                'source_function':'phase_5_cement.calculate_base_results / engineering_tools.calculate_slurry_from_components'},
           'Mixing Tank Selected in Word':None,'Total Preparation Water Reported in Word':None,
           'Dead Volume Included by Engineer':None,'reason':'Missing uniquely proved source preparation NOTE'}
        water.append(f)
        if inspected['ct_job'] or fluid not in active:
            f['reason']='CT/Scavenger/nonordinary role not verified in C03';continue
        candidates=groups.get(fluid,[])
        if unassigned or len(candidates)!=1 or not candidates[0]['complete'] or len(candidates[0]['notes'])!=1:
            f['reason']='Missing/duplicate group or NOTE, or unassigned cement preparation statement';continue
        group=candidates[0];r=group['notes'][0]
        f.update(locator=r['locator'],raw_text=r['raw_text'],note=r['note'],step=r['step'],section=r['section'],source_order=r['source_order'],
                 proof_table_locators=group['table_locators'])
        if note_counts[r['note']]!=1:f['reason']='Duplicate preparation NOTE identity';continue
        match=NOTE.fullmatch(' '.join(r['raw_text'].split()))
        if not match:f['reason']='Malformed source preparation NOTE pattern';continue
        raw,unit,state=total_token(match['water']);tank=match['tank']
        f.update(**{'Mixing Tank Selected in Word':tank,
                    'Total Preparation Water Reported in Word':{'raw':raw,'unit':unit,'state':state,'display_decimals':1}})
        if tank not in inspected['allowed_tanks']:f['reason']='Unknown or source-job-unavailable tank label';continue
        if unit!='bbl':f['reason']='Unknown preparation-water unit';continue
        if state not in ('NUMBER','ZERO','NEGATIVE'):f['reason']='Missing/dash/N/A/malformed water or unproven precision';continue
        inferred=infer(raw,s['calc']['field_water_bbl']);f['Dead Volume Included by Engineer']=inferred
        conflict=any(p['fluid']==fluid and (p['tank']!=tank or Decimal(p['total'])!=Decimal(raw)) for p in procedures)
        if conflict:f['reason']='Contradictory uniquely named single-slurry Procedure tank/water';continue
        if inferred['samples'] is None:f['reason']='Negative/inconsistent total against original source allowance domain';continue
        f.update(status='INFERRED_AT_DISPLAY_PRECISION',reason='Claimed included allowance, not independently measured or physically validated')
        allowances[fluid]=inferred['samples']
    projections=request({'action':'gross','operator':operator,'allowances':allowances}) if allowances else None
    gross=[]
    grouped=defaultdict(list)
    for r in parsed['records']:
        if r['section']=='cement' and r['locator'].get('table') is not None:
            loc=r['locator'];grouped[(loc['body_block'],loc['table'],tuple(loc['table_path']),loc['row'])].append(r)
    candidates=[]
    for rows in grouped.values():
        rows=sorted(rows,key=lambda r:r['locator']['column']);fluid=rows[0]['association']
        if fluid not in active or rows[0]['table_anchor']!=fluid+' '+SUFFIXES[2]:continue
        cells=defaultdict(list)
        for r in rows:cells[r['locator']['column']].append(r)
        if set(cells)!=set(range(7)) or any(len(x)!=1 for x in cells.values()):continue
        name=cells[1][0]['raw_text'];kind=cells[2][0]['raw_text'];r=cells[6][0]
        if ''.join((r['column_label'] or '').split()).casefold()!='lbsorgal(withdeadvol.)' or name=='Name':continue
        g={'slurry':fluid,'material':name,'material_type':kind,'status':'NOT_VERIFIABLE',
           'locator':r['locator'],'raw_text':r['raw_text'],'source_order':r['source_order'],'section':r['section'],
           'printed_label':r['printed_label'],'column_label':r['column_label'],'source_document_sha256':parsed['source_document_sha256'],
           'source_sha':PIN,'source_function':'phase_5_cement.build_cement_tables',
           'reason':'No uniquely valid water/tank or material association'}
        gross.append(g);candidates.append((g,rows))
    counts=Counter((g['slurry'],g['material'],g['material_type']) for g in gross)
    for g,rows in candidates:
        fluid=g['slurry']
        if fluid not in allowances or counts[(fluid,g['material'],g['material_type'])]!=1:continue
        if any(r['association_state']!='EXPLICIT' for r in rows):continue
        source_headers=('Item','Name','Material Type','lbs or gal','(lbs or gal)/sk','(lbs or gal)/bbl','lbs or gal (with dead Vol.)')
        if [''.join((r['column_label'] or '').split()) for r in rows]!=[''.join(x.split()) for x in source_headers]:
            g['reason']='Unproved source material/quantity column labels';continue
        expected=[]
        for label,p in projections['projections'][fluid].items():
            match=[r for r in p['additives'] if r['Name']==g['material'] and r['Material Type']==g['material_type']]
            if len(match)!=1:expected=[];break
            expected.append((label,match[0]['lbs or gal (with dead Vol.)']))
        if not expected:continue
        units={'gal' if text.endswith(' gal') else '' for _,text in expected}
        if len(units)!=1:continue
        unit=units.pop()
        sys.path.insert(0,str(HERE.parent/'c02'))
        from c02_compare import number
        reported,state=number(g['raw_text'],unit);g.update(reported_state=state,unit=unit or 'lb',source_display_projections=dict(expected))
        values=[number(t,unit)[0] for _,t in expected]
        if reported is None or any(x is None for x in values):continue
        g['delta_to_source_display_projections']={label:str(reported-value) for (label,_),value in zip(expected,values)}
        g['tolerance_at_source_display']=0
        lo,hi=min(values),max(values);g['conservative_source_display_range']=[str(lo),str(hi)]
        if reported<lo or reported>hi:g.update(status='DISCREPANCY',reason='Outside all conservative source-compatible displayed gross quantities')
        elif lo==hi:g.update(status='MATCH_AT_DISPLAY_PRECISION',reason='Original source display is invariant over conservative inferred interval; not exact DV proof')
        else:g.update(status='INFERRED_AT_DISPLAY_PRECISION',reason='Compatible with source display enclosure; inferred allowance is nonunique, not an exact MATCH')
    return {'schema':'c03.1','parser_schema':parsed['schema_version'],'status':'PARTIAL_FINDINGS_ONLY','source_sha':PIN,
        'source_document_sha256':parsed['source_document_sha256'],'c02':baseline,
        'water_findings':water,'gross_additive_findings':gross,'procedure_water_evidence':procedures,
        'unassigned_preparation_records':unassigned,'source_projections':projections,
        'limitations':['Not an independent measurement/tank heel or whole-program PASS',
            'Spacer/operational spacer/CT/Scavenger/corrections/full procedure not verified']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operator_json');p.add_argument('docx');a=p.parse_args()
    try:
        op_path=Path(a.operator_json).resolve(strict=True)
        if not op_path.is_relative_to(HERE):raise ValueError('Operator input outside c03')
        sys.path.insert(0,str(HERE.parent/'c02'))
        from c02_engine import read_json
        result=analyze(a.docx,read_json(op_path.read_text()))
    except (ValueError,OSError,TypeError) as error:result={'status':'INPUT_REJECTED','reason':str(error)}
    print(json.dumps(result,allow_nan=False,indent=2));return 0 if result['status']=='PARTIAL_FINDINGS_ONLY' else 2


if __name__=='__main__':raise SystemExit(main())
