#!/usr/bin/env python3
"""Compare the actual engine Sticker callback source without building Horizon."""
import hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    started=time.monotonic()
    out=ROOT/'.local/sticker-completion';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'.local/patched-launcher/native/source/9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0/crates/horizon-world/src/create_sticker.rs'
    patch=(ROOT/'patches/horizon-zz-sticker-completion.patch').read_text()
    section=patch.split('+++ b/crates/horizon-world/src/create_sticker.rs\n',1)[1].split('--- ',1)[0]
    canonical=''.join(line[1:] for line in section.splitlines(True) if line.startswith('+'))
    assert source.read_text()==canonical,'Prepared callback source differs from the canonical engine patch'
    rows=[json.loads(line) for line in (ROOT/'fixtures/sticker-remaining-java.jsonl').read_text().splitlines()]
    meta=json.loads((ROOT/'fixtures/sticker-remaining-java.metadata.json').read_text())
    assert meta['patch_sha256']==hashlib.sha256((ROOT/'tools/java-sticker-remaining.patch').read_bytes()).hexdigest()
    code='#[path='+json.dumps(str(source))+'] mod sticker;\nfn main(){\n'
    expected=[]
    for row in rows:
        up=str(row.get('facing')=='up').lower();careful=str(row.get('careful',False)).lower()
        if row['kind']=='physics':
            living=str(row['living']).lower();vy=repr(row['vy']);i=len(expected)
            code+=f'let b=sticker::bounce([0.5,{vy},0.25],{up},{living},{careful});let s=sticker::step([0.5,{vy},0.25],{up},{careful});println!("{{}} {{}} {{}} {{}} {{}} {{}}",b[0].to_bits(),b[1].to_bits(),b[2].to_bits(),s[0].to_bits(),s[1].to_bits(),s[2].to_bits());\n'
            expected.append(row['bounce']+row['step'])
        elif row['kind']=='fall':
            code+=f'println!("{{}}",sticker::fall_calls({up},{careful}));\n';expected.append([str(row['damage_calls'])])
    code+='}\n';harness=out/'callbacks.rs';harness.write_text(code)
    rust=ROOT/'.local/patched-launcher/rust/1.99.1-aarch64-apple-darwin/bin/rustc'
    subprocess.run([str(rust),'--edition=2024','-O',str(harness),'-o',str(out/'callbacks')],check=True)
    run=subprocess.run([str(out/'callbacks')],capture_output=True,text=True,check=True)
    actual=[line.split() for line in run.stdout.splitlines()]
    assert len(actual)==len(expected)==504
    for i,(a,b) in enumerate(zip(actual,expected)):assert a==b,(i,a,b)
    (out/'callback-core-summary.json').write_text(json.dumps({'physics_cases':384,'fall_call_cases':120,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'result':'pass','seconds':time.monotonic()-started},indent=2)+'\n')
    print('384 bit-exact production physics callbacks and120 fall-call counts match Java; no Horizon build or game launch.')
if __name__=='__main__':main()
