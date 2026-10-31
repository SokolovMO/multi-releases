import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import releasekit as r
from release_manifest import create,verify

class FeedTests(unittest.TestCase):
    def test_stable_and_beta_survive_with_monotonic_order(self):
        common={'version':'0.4.0','minimum_macos':'15.0'}
        items=[({**common,'channel':'stable','build':'64'},'https://example.test/stable.dmg',10,'a'),({**common,'channel':'beta','build':'65'},'https://example.test/beta.dmg',11,'b')]
        root=ET.fromstring(r.render_feed('MultiSwitcher',items))
        entries=root.findall('channel/item')
        self.assertEqual([e.find('{'+r.NS+'}version').text for e in entries],['65','64'])
        self.assertEqual(entries[0].find('{'+r.NS+'}channel').text,'beta')
        self.assertIsNone(entries[1].find('{'+r.NS+'}channel'))
        self.assertEqual(entries[0].find('enclosure').attrib['{'+r.NS+'}cpuArchitecture'],'arm64')
    def test_tag_and_channel_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):r.validate_tag('v0.4.0-build64','beta','0.4.0','64')
    def test_feed_signature_with_real_sparkle(self):
        binary=os.environ.get('SPARKLE_SIGN_UPDATE')
        if not binary:self.skipTest('set SPARKLE_SIGN_UPDATE for real signing integration')
        # Ephemeral fixture key, never used for production delivery.
        key=base64.b64encode(hashlib.sha256(b'multi-release-test-fixture').digest())
        with tempfile.TemporaryDirectory() as temp:
            feed=Path(temp)/'appcast.xml';feed.write_bytes(r.render_feed('MultiShift',[]))
            r.sign(binary,key,feed)
            self.assertIn(b'sparkle-signatures',feed.read_bytes())
            subprocess.run([binary,'--verify','--ed-key-file','-',str(feed)],input=key,check=True,capture_output=True)
            feed.write_bytes(feed.read_bytes().replace(b'MultiShift',b'MultiShifX'))
            result=subprocess.run([binary,'--verify','--ed-key-file','-',str(feed)],input=key,capture_output=True)
            self.assertNotEqual(result.returncode,0)
if __name__=='__main__':unittest.main()
