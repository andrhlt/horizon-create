#!/usr/bin/env python3
"""Capture the pinned TrainStatusDisplaySource in a disposable Java checkout."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import time

ROOT=Path(__file__).resolve().parents[1]
PIN='ac0c444d9828da3453ae8cc65338e8de063286fb'

def record(log,elapsed):
    rows=[{'case':case,'text':value} for case,value in re.findall(r'CREATE_TRAIN_FEEDBACK ([^|\n]+)\|([^\r\n]*)',log)]
    assert len(rows)==11,rows
    target=ROOT/'fixtures/train-feedback-java.json'
    target.write_text(json.dumps(rows,indent=2)+'\n')
    patch=ROOT/'tools/java-train-feedback.patch'
    target.with_suffix('.metadata.json').write_text(json.dumps({'revision':PIN,'patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),'records':len(rows),'seconds':elapsed,'scope':'Controlled Java TrainStatusDisplaySource, six delay-format snapshots, four blank-state boundaries and ArrivalSoundQueue endpoints. No moving Java train, packet or audio capture.'},indent=2)+'\n')

def main():
    start=time.monotonic()
    with TemporaryDirectory(prefix='train-feedback-java-') as tmp:
        checkout=Path(tmp)/'Create'
        subprocess.run(['git','clone','--shared','--no-checkout',str(ROOT/'.local/java-reference'),str(checkout)],check=True)
        subprocess.run(['git','checkout','--detach',PIN],cwd=checkout,check=True)
        subprocess.run(['git','apply',str(ROOT/'tools/java-train-feedback.patch')],cwd=checkout,check=True)
        env=os.environ|{'JAVA_HOME':'/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home'}
        result=subprocess.run(['./gradlew','--offline','runGameTestServer'],cwd=checkout,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=result.stdout.decode(errors='replace')
        (ROOT/'.local/java-feedback-capture.log').write_text(log)
        assert result.returncode==0,log[-3000:]
        record(log,time.monotonic()-start)

if __name__=='__main__':main()
