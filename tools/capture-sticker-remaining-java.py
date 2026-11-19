#!/usr/bin/env python3
"""Capture the original Sticker block callbacks and support-face decisions."""
import collections,gzip,hashlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PIN='ac0c444d9828da3453ae8cc65338e8de063286fb'
TRAJECTORY_SETUP={'initial_relative_position': [0.5, 1, 0.5], 'initial_motion': [0.2, 0, 0.1], 'pig_ai': 'enabled, goals and target goals cleared', 'scenarios': {'0': 'up Sticker, retracted', '1': 'north Sticker, retracted', '2': 'stone'}, 'ticks': 5, 'rig_chunk_offsets': [2, 6, 10], 'comparison': 'Decode double bits; positions contain large-world coordinate rounding, use explicit position tolerance in integration comparison.'}
def main():
    (ROOT/'.local/sticker-benchmark').mkdir(parents=True,exist_ok=True)
    patch=(ROOT/'tools/java-sticker-remaining.patch').read_bytes()
    with tempfile.TemporaryDirectory(prefix='sticker-remaining-java-') as tmp:
        checkout=Path(tmp)/'create'
        subprocess.run(['git','clone','--shared','--no-checkout',str(ROOT/'.local/java-reference'),str(checkout)],check=True)
        subprocess.run(['git','checkout','--detach',PIN],cwd=checkout,check=True)
        applied=Path(tmp)/'oracle.patch';applied.write_bytes(patch)
        subprocess.run(['git','apply',str(applied)],cwd=checkout,check=True)
        shutil.rmtree(checkout/'run/world',ignore_errors=True)
        env={**os.environ,'JAVA_HOME':'/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home'}
        start=time.monotonic();result=subprocess.run(['./gradlew','--offline','runGameTestServer'],cwd=checkout,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);elapsed=time.monotonic()-start
        with gzip.open(ROOT/'.local/sticker-benchmark/java-remaining.log.gz','wb') as log:log.write(result.stdout)
        rows=[json.loads(line.split('STICKER_REMAINING ',1)[1]) for line in result.stdout.decode(errors='replace').splitlines() if 'STICKER_REMAINING {' in line]
        counts=dict(collections.Counter(row['kind'] for row in rows))
        assert result.returncode==0 and counts=={'physics':384,'fall':120,'face':480,'trajectory':15},(result.returncode,counts)
        rows.sort(key=lambda row:json.dumps(row,sort_keys=True))
        (ROOT/'fixtures/sticker-remaining-java.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        (ROOT/'fixtures/sticker-remaining-java.metadata.json').write_text(json.dumps({'revision':PIN,'patch_sha256':hashlib.sha256(patch).hexdigest(),'records':len(rows),'counts':counts,'face_setup':{'stone_below':True,'actual_block_asserted':True},'trajectory_setup':TRAJECTORY_SETUP,'seconds':elapsed,'scope':'Actual StickerBlock callbacks (bounce, stepOn, fallOn) and BlockMovementChecks/SuperGlue face queries; direct callbacks plus three five-tick AI-enabled pig trajectories with cleared goal selectors, no client/LAN comparison'},indent=2)+'\n')
        print(json.dumps({'records':len(rows),'counts':counts,'face_setup':{'stone_below':True,'actual_block_asserted':True},'trajectory_setup':TRAJECTORY_SETUP,'seconds':elapsed}),flush=True)
if __name__=='__main__':main()
