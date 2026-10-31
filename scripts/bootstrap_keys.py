"""Provision independent Sparkle seeds without printing private material.
Run locally after creating the public distribution repository. Back up the key
folder in an encrypted store. Reuses existing seeds; never silently rotates.
"""
import base64
import os
from pathlib import Path
import subprocess

root=Path.home()/"Library/Application Support/MultiReleases/Signing"
root.mkdir(parents=True,exist_ok=True,mode=0o700)
for app in ("MultiShift","MultiSwitcher"):
    path=root/(app+".seed")
    if not path.exists():
        with path.open('xb') as stream:
            os.chmod(path,0o600)
            stream.write(os.urandom(32))
    seed=path.read_bytes()
    if len(seed)!=32:raise ValueError('invalid stored seed')
    private_der=bytes.fromhex('302e020100300506032b657004220420')+seed
    public_der=subprocess.run(['openssl','pkey','-inform','DER','-pubout','-outform','DER'],input=private_der,capture_output=True,check=True).stdout
    public=base64.b64encode(public_der[-32:])
    # Sparkle's exported key file contains base64 seed; GitHub secret contains
    # base64 of that exported file, matching the release workflow convention.
    exported=base64.b64encode(seed)
    secret=base64.b64encode(exported)
    subprocess.run(['gh','secret','set',app.upper()+'_SPARKLE_PRIVATE_KEY_BASE64','--repo','SokolovMO/multi-releases','--env','public-delivery'],input=secret,check=True,stdout=subprocess.DEVNULL)
    for repo,env in [('multi-releases','public-delivery'),(app,'multishift-release' if app=='MultiShift' else 'multiswitcher-release')]:
        subprocess.run(['gh','variable','set',app.upper()+'_SPARKLE_PUBLIC_KEY','--repo','SokolovMO/'+repo,'--env',env],input=public,check=True,stdout=subprocess.DEVNULL)
    print(app+': independent key provisioned; encrypted backup required')
print('Private material stays in '+str(root))
