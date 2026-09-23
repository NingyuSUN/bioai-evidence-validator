"""Rebuild the exact projection/reference set from the pinned upstream OBO file.

Download the manifest's upstream_url yourself, then pass --obo and a fresh --output.
No network access, source updates, or automatic acceptance of changed inputs occurs.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from pipeline import ROOT, digest, normalized


def project(raw: bytes) -> list[dict]:
    text=raw.decode('utf-8');terms={};line=1
    for block in text.split('\n\n'):
        identity=re.search(r'^id: (VBO:\d+)$',block,re.M)
        if block.startswith('[Term]') and identity:
            terms[identity[1]]={'block':block,'line':line,'parents':re.findall(r'^is_a: (\S+)',block,re.M)}
        line += block.count('\n')+2
    memo={}
    def dog(key,seen=frozenset()):
        if key=='VBO:0400024':return True
        if key in seen:return False
        if key not in memo:
            memo[key]=any(dog(p,seen|{key}) for p in terms.get(key,{}).get('parents',[]))
        return memo[key]
    def decode(value):
        return re.sub(r'\\(.)',lambda m:{'n':'\n','t':'\t'}.get(m[1],m[1]),value)
    rows=[]
    for key,term in sorted(terms.items()):
        block=term['block']
        if key=='VBO:0400024' or not dog(key) or re.search(r'^is_obsolete: true$',block,re.M):continue
        name=re.search(r'^name: (.+)$',block,re.M)[1]
        synonyms=sorted(set(decode(s) for s in re.findall(r'^synonym: "((?:[^"\\]|\\.)*)" EXACT(?: |\[)',block,re.M)))
        rows.append({'id':key,'name':name,'exact_synonyms':synonyms,'is_a':term['parents'],'upstream_line':term['line']})
    return rows


def reference(rows):
    index=defaultdict(set);spelling={};canonical=set()
    for term in rows:
        canonical.add(normalized(term['name']))
        for label in [term['name'],*term['exact_synonyms']]:
            index[normalized(label)].add(term['id']);spelling.setdefault(normalized(label),label)
    groups={'unique_canonical':[],'unique_synonym':[],'ambiguous_name':[]}
    for name,ids in index.items():
        group='ambiguous_name' if len(ids)>1 else 'unique_canonical' if name in canonical else 'unique_synonym'
        groups[group].append(name)
    cases=[]
    for group,names in groups.items():
        for name in sorted(names,key=lambda n:digest(('bioai-vbo-v1:'+n).encode()))[:24]:
            cases.append({'case_id':'vbo-'+digest(name.encode())[:12],'stratum':group,'query':spelling[name],
                          'expected_candidates':sorted(index[name]),'expected_status':'rejected' if group=='ambiguous_name' else 'admitted',
                          'reference_basis':'Cardinality of casefolded whitespace-normalized canonical names and EXACT synonyms in the full frozen dog projection; automatic unambiguous name mapping contract.'})
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--obo',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads((ROOT/'sources/manifest.json').read_text(encoding='utf-8'))
    raw=args.obo.read_bytes()
    if digest(raw)!=manifest['upstream_sha256']:raise ValueError('Upstream release hash mismatch')
    rows=project(raw)
    data=(json.dumps(rows,ensure_ascii=False,indent=2)+'\n').encode()
    if digest(data)!=manifest['projection_sha256']:raise ValueError('Projection differs from frozen source')
    cases=(json.dumps(reference(rows),ensure_ascii=False,indent=2)+'\n').encode()
    if cases!=(ROOT/'reference_cases.json').read_bytes():raise ValueError('Reference set differs')
    if args.output.exists():raise ValueError('Use a new output directory')
    args.output.mkdir(parents=True)
    (args.output/'vbo-dogs.json').write_bytes(data)
    (args.output/'reference_cases.json').write_bytes(cases)
    print(f'Rebuilt {len(rows)} terms and 72 source-derived reference cases; both match byte-for-byte.')


if __name__=='__main__':main()
