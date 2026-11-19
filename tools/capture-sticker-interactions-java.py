#!/usr/bin/env python3
"""Capture the original Sticker wrench rotation and weak-power policy."""
import gzip,hashlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PIN='ac0c444d9828da3453ae8cc65338e8de063286fb'
def main():
    (ROOT/'.local/sticker-benchmark').mkdir(parents=True,exist_ok=True)
    patch=(ROOT/'tools/java-sticker-interactions.patch').read_bytes()
    with tempfile.TemporaryDirectory(prefix='sticker-interactions-java-') as tmp:
        checkout=Path(tmp)/'create'
        subprocess.run(['git','clone','--shared','--no-checkout',str(ROOT/'.local/java-reference'),str(checkout)],check=True)
        subprocess.run(['git','checkout','--detach',PIN],cwd=checkout,check=True)
        applied=Path(tmp)/'oracle.patch';applied.write_bytes(patch)
        subprocess.run(['git','apply',str(applied)],cwd=checkout,check=True)
        shutil.rmtree(checkout/'run/world',ignore_errors=True)
        env={**os.environ,'JAVA_HOME':'/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home'}
        start=time.monotonic();result=subprocess.run(['./gradlew','--offline','runGameTestServer'],cwd=checkout,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);elapsed=time.monotonic()-start
        with gzip.open(ROOT/'.local/sticker-benchmark/java-interactions.log.gz','wb') as log:log.write(result.stdout)
        rows=[json.loads(line.split('STICKER_INTERACTIONS ',1)[1]) for line in result.stdout.decode(errors='replace').splitlines() if 'STICKER_INTERACTIONS {' in line]
        assert result.returncode==0 and len(rows)==42,(result.returncode,len(rows))
        (ROOT/'fixtures/sticker-interactions-java.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        metadata={'revision':PIN,'patch_sha256':hashlib.sha256(patch).hexdigest(),'records':len(rows),'seconds':elapsed,'scope':'Actual Sticker.getRotatedBlockState for six initial directions times six targeted faces, extended/powered preserved; shouldCheckWeakPower in six directions. Dedicated Java GameTest without client/GPU.'}
        defaults=ROOT/'fixtures/sticker-defaults-java.jsonl'
        if defaults.exists():
            receipt=json.loads((ROOT/'fixtures/sticker-defaults-java.metadata.json').read_text())
            assert receipt['revision']==PIN and receipt['patch_sha256']==hashlib.sha256((ROOT/'tools/java-sticker-defaults.patch').read_bytes()).hexdigest()
            metadata['defaults']=json.loads(defaults.read_text())
            metadata['defaults_evidence']={'fixture':'fixtures/sticker-defaults-java.jsonl','metadata':'fixtures/sticker-defaults-java.metadata.json','patch_sha256':receipt['patch_sha256']}
        (ROOT/'fixtures/sticker-interactions-java.metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(json.dumps({'records':len(rows),'seconds':elapsed}),flush=True)
if __name__=='__main__':main()
