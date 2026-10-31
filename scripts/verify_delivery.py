"""Verify the deployed feed bytes and public artifact endpoints after Pages deploy."""
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

for app in ('MultiShift','MultiSwitcher'):
    base='https://sokolovmo.github.io/multi-releases/'+app+'/'
    for name in ('appcast.xml','releases.json'):
        expected=(Path('site')/app/name).read_bytes()
        for attempt in range(12):
            try:
                request=Request(base+name+'?delivery='+hashlib.sha256(expected).hexdigest(),headers={'Cache-Control':'no-cache'})
                with urlopen(request,timeout=15) as response:actual=response.read()
                if actual==expected:break
            except Exception:pass
            time.sleep(5)
        else:raise SystemExit('deployed bytes do not match: '+app+'/'+name)
    for release in json.loads((Path('site')/app/'releases.json').read_text()):
        request=Request(release['url'],method='HEAD')
        with urlopen(request,timeout=30) as response:
            if response.status!=200:raise SystemExit('artifact unavailable')
print('deployed feeds and artifact endpoints verified')
