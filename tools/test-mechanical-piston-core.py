#!/usr/bin/env python3
"""Compare production piston placement-mode decisions with original Java endpoints."""
import hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 started=time.monotonic();out=ROOT/'.local/mechanical-piston';out.mkdir(parents=True,exist_ok=True)
 meta=json.loads((ROOT/'fixtures/mechanical-piston-modes-java.metadata.json').read_text())
 assert meta['patch_sha256']==hashlib.sha256((ROOT/'tools/java-mechanical-piston-modes.patch').read_bytes()).hexdigest()
 rows=[json.loads(line) for line in (ROOT/'fixtures/mechanical-piston-modes-java.jsonl').read_text().splitlines()]
 cases=[r for r in rows if not r['pending'] and ((r['offset']==1 and r['speed']<0) or (r['offset']==0 and r['speed']>0))]
 assert {r['case'] for r in cases}=={0,1,2} and len(cases)>=18
 source=ROOT/'native/piston_motion.rs';program='#[path='+json.dumps(str(source))+'] mod piston;\nfn main(){\n'
 for r in cases:program+=f'println!("{{}}",piston::should_place({r["mode"]},0,{r["offset"]}));\n'
 program+='}\n';(out/'core-replay.rs').write_text(program)
 rust=ROOT/'.local/patched-launcher/rust/1.99.1-aarch64-apple-darwin/bin/rustc'
 subprocess.run([str(rust),'--edition=2024','-O',str(out/'core-replay.rs'),'-o',str(out/'core-replay')],check=True)
 result=subprocess.run([str(out/'core-replay')],capture_output=True,text=True,check=True)
 actual=[line=='true' for line in result.stdout.splitlines()];expected=[not row['running'] for row in cases]
 assert actual==expected,[(r,a,e) for r,a,e in zip(cases,actual,expected) if a!=e]
 receipt={'cases':len(cases),'modes':[0,1,2],'seconds':time.monotonic()-started,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'result':'pass'}
 (out/'core-summary.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
