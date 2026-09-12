"""Exercise real LAN certificates without touching the running installation."""

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_transfers import prepare_tls


class CertificateTest(unittest.TestCase):
    def test_dns_and_ip_certificates_are_trusted_and_preserved(self):
        for host, flag in [('chat.zohenhl.ovh', '-verify_hostname'), ('192.0.2.10', '-verify_ip')]:
            with self.subTest(host=host), TemporaryDirectory() as directory:
                state = Path(directory)
                prepare_tls(state, host)
                tls = state / 'tls'
                certificate = (tls / 'server.crt').read_bytes()
                key = (tls / 'server.key').read_bytes()
                result = subprocess.run(['openssl', 'verify', '-CAfile', str(tls / 'ca.crt'),
                                         flag, host, str(tls / 'server.crt')], capture_output=True)
                self.assertEqual(result.returncode, 0)
                prepare_tls(state, host)
                self.assertEqual(certificate, (tls / 'server.crt').read_bytes())
                self.assertEqual(key, (tls / 'server.key').read_bytes())
