#!/usr/bin/env python3
"""Run the pinned Java mechanical-piston and extended-Sticker trace headlessly."""
import gzip,hashlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PIN='ac0c444d9828da3453ae8cc65338e8de063286fb'
def main():
 out=ROOT/'.local/mechanical-piston';out.mkdir(parents=True,exist_ok=True)
 patch=ROOT/'tools/java-mechanical-piston-sticker.patch'
 with tempfile.TemporaryDirectory(prefix='piston-java-') as tmp:
  checkout=Path(tmp)/'create'
  subprocess.run(['git','clone','--shared','--no-checkout',str(ROOT/'.local/java-reference'),str(checkout)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run(['git','checkout','--detach',PIN],cwd=checkout,check=True,stdout=subprocess.DEVNULL)
  subprocess.run(['git','apply',str(patch)],cwd=checkout,check=True)
  shutil.rmtree(checkout/'run/world',ignore_errors=True)
  env={**os.environ,'JAVA_HOME':'/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home'}
  start=time.monotonic();result=subprocess.run(['./gradlew','--offline','runGameTestServer'],cwd=checkout,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);elapsed=time.monotonic()-start
  (out/'java.log').write_bytes(result.stdout)
  rows=[json.loads(line.split('CREATE_PISTON_STICKER ',1)[1]) for line in result.stdout.decode(errors='replace').splitlines() if 'CREATE_PISTON_STICKER {' in line]
  assert result.returncode==0 and len(rows)==24 and any(row["running"] and "create:sticker" in row["payload"] and "minecraft:stone" in row["payload"] and row["captured_extended"] for row in rows),(result.returncode,len(rows),str(out/'java.log'))
  (ROOT/'fixtures/mechanical-piston-sticker-java.jsonl').write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
  (ROOT/'fixtures/mechanical-piston-sticker-java.metadata.json').write_text(json.dumps({'revision':PIN,'patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),'records':len(rows),'seconds':elapsed,'scope':'Actual Java mechanical piston with extended Sticker and stone, 24 ticks including a reversal'},indent=2)+'\n')
  print(json.dumps({'records':len(rows),'seconds':elapsed}))
if __name__=='__main__':main()
