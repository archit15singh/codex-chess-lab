"""Exact inclusive family sign-flip references; no resampling or scoring.

Raw JSON decimals are interpreted exactly. Common units are selected across all
supplied arms, and every retained source family has equal weight.
"""
from decimal import Decimal
from fractions import Fraction
from itertools import combinations,product
from math import isfinite

def rational(value):
    if isinstance(value,Fraction):return value
    if type(value) is int:return Fraction(value)
    if type(value) is float and isfinite(value):return Fraction(str(value))
    if isinstance(value,Decimal) and value.is_finite():return Fraction(value)
    raise ValueError('endpoint must be a finite JSON number or null')

def exact_reference(rows,arms):
    if not isinstance(arms,list) or len(arms)<2 or any(not isinstance(a,str) or not a for a in arms) or len(set(arms))!=len(arms):raise ValueError('distinct arms required')
    if not isinstance(rows,list) or not rows:raise ValueError('assigned rows required')
    seen=set();assigned={};matched={};available={a:0 for a in arms};unmatched=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'unit','family','values'}:raise ValueError('invalid row keys')
        unit,family,values=row['unit'],row['family'],row['values']
        if not isinstance(unit,str) or not unit or unit in seen or not isinstance(family,str) or not family or not isinstance(values,dict) or set(values)!=set(arms):raise ValueError('invalid unit/family/arm identity')
        seen.add(unit);assigned.setdefault(family,[]).append(unit);parsed={}
        for a in arms:
            parsed[a]=None if values[a] is None else rational(values[a]);available[a]+=parsed[a] is not None
        if all(parsed[a] is not None for a in arms):matched.setdefault(family,[]).append(parsed)
        else:unmatched.append(unit)
    names=sorted(matched);k=len(names)
    if k>16:raise ValueError('exact enumeration limited to16families')
    means={f:{a:sum((r[a] for r in matched[f]),Fraction())/len(matched[f]) for a in arms} for f in names};contrasts=[]
    for left,right in combinations(arms,2):
        differences={f:means[f][right]-means[f][left] for f in names}
        estimate=sum(differences.values(),Fraction())/k if k else None
        tail=sum(abs(sum((differences[f]*s for f,s in zip(names,signs)),Fraction())/k)>=abs(estimate) for signs in product([-1,1],repeat=k)) if k else None
        reference={'assignments':2**k,'two_sided_p':tail/2**k} if k else None
        contrasts.append({'left':left,'right':right,'exact_estimate':str(estimate) if k else None,'exact_family_differences':{f:str(v) for f,v in differences.items()},'inclusive_tail_assignments':tail,'sign_flip_reference':reference})
    return {'assigned_units':len(rows),'assigned_families':len(assigned),'available_units_by_arm':available,'common_units':sum(map(len,matched.values())),'common_families':k,'unmatched_units':unmatched,'families_without_common_units':sorted(set(assigned)-set(names)),'family_means':{f:{a:str(v) for a,v in x.items()} for f,x in means.items()},'contrasts':contrasts}
