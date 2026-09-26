"""Apply the reviewed delivery changes to sibling monitor working copies."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGETS = {
    'monitor-policia': ('sisc_heartbeat.py', 'monitor.yml'),
    'monitor-mindefensa': ('sisc_heartbeat.py', 'monitor.yml'),
    'monitor-siedco': ('sisc_heartbeat.py', 'monitor_siedco.yml'),
    'monitor-valle': ('src/integrations/sisc_heartbeat.py', 'extract_jamundi.yml'),
}

OLD = '''    try:
        with urlopen(request, timeout=timeout) as response:
            accepted = 200 <= response.status < 300
        print(f"[INFO] Heartbeat SISC enviado ({payload['status']}).")
        return accepted
    except HTTPError as error:
        print(f"[AVISO] El API SISC rechazo el heartbeat (HTTP {error.code}).")
    except (URLError, TimeoutError, OSError) as error:
        print(f"[AVISO] No se pudo enviar el heartbeat SISC: {error}.")
    return False'''
NEW = '''    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                accepted = 200 <= response.status < 300
            print(f"[INFO] Heartbeat SISC enviado ({payload['status']}).")
            return accepted
        except HTTPError as error:
            print(f"[AVISO] El API SISC rechazo el heartbeat (HTTP {error.code}).")
            if error.code not in {408, 429, 500, 502, 503, 504}:
                return False
        except (URLError, TimeoutError, OSError):
            print(f"[AVISO] Fallo temporal de entrega SISC; intento {attempt + 1}/3.")
        if attempt < 2:
            time.sleep(2 ** (attempt + 1))
    return False'''

ARTIFACT = '''
      - name: Conservar reporte SISC para sincronizacion local
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sisc-heartbeat
          path: sisc-heartbeat.json
          if-no-files-found: warn
          retention-days: 30
'''

TEST = '''import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import MODULE as heartbeat


class DeliveryTests(unittest.TestCase):
    def test_timeout_retries_then_accepts(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.status = 200
        with patch.object(heartbeat, "urlopen", side_effect=[TimeoutError(), response]) as send, patch.object(heartbeat.time, "sleep"):
            self.assertTrue(heartbeat.send_heartbeat({"status": "CURRENT"}, oidc_token="test"))
            self.assertEqual(send.call_count, 2)

    def test_permanent_error_not_retried(self):
        error = HTTPError("https://example.test", 404, "missing", {}, None)
        with patch.object(heartbeat, "urlopen", side_effect=error) as send, patch.object(heartbeat.time, "sleep"):
            self.assertFalse(heartbeat.send_heartbeat({"status": "CURRENT"}, oidc_token="test"))
            self.assertEqual(send.call_count, 1)

    def test_retry_exhaustion(self):
        with patch.object(heartbeat, "urlopen", side_effect=TimeoutError()) as send, patch.object(heartbeat.time, "sleep"):
            self.assertFalse(heartbeat.send_heartbeat({"status": "CURRENT"}, oidc_token="test"))
            self.assertEqual(send.call_count, 3)
'''

for repo, (module, workflow) in TARGETS.items():
    root = ROOT / repo
    path = root / module
    content = path.read_text(encoding='utf-8')
    if OLD not in content:
        raise RuntimeError(f'Unexpected source or changes already applied: {path}')
    content = content.replace('import os\n', 'import os\nimport time\n', 1)
    content = content.replace('timeout: int = 20,', 'timeout: int = 60,')
    content = content.replace(OLD, NEW, 1)
    marker = '    print(\n        "[INFO] Estado para Centro de fuentes: "'
    assert marker in content
    content = content.replace(marker, '    Path("sisc-heartbeat.json").write_text(\n'
                              '        json.dumps(payload, ensure_ascii=True), encoding="utf-8"\n'
                              '    )\n' + marker, 1)
    path.write_text(content, encoding='utf-8')
    wf = root / '.github/workflows' / workflow
    wf.write_text(wf.read_text(encoding='utf-8').rstrip() + '\n' + ARTIFACT, encoding='utf-8')
    (root / 'test_sisc_delivery.py').write_text(TEST.replace('MODULE', module.removesuffix('.py').replace('/', '.')), encoding='utf-8')

root = ROOT / 'monitor-fiscalia-spoa-v3'
path = root / 'src/spoa_monitor/sisc.py'
content = path.read_text(encoding='utf-8')
content = content.replace('import os\n', 'import os\nimport time\nfrom pathlib import Path\n', 1)
marker = '        return self.post("source-center/heartbeat", payload)'
assert marker in content
content = content.replace(marker, '''        # Persist before delivery: an unavailable server must not lose this report.
        Path("sisc-heartbeat.json").write_text(
            json.dumps(payload, ensure_ascii=True, default=str), encoding="utf-8"
        )
        for attempt in range(3):
            try:
                return self.post("source-center/heartbeat", payload, timeout=60)
            except HTTPError as error:
                if error.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                    raise
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise
            time.sleep(2 ** (attempt + 1))''', 1)
path.write_text(content, encoding='utf-8')
wf = root / '.github/workflows/monitor_spoa_v3.yml'
wf.write_text(wf.read_text(encoding='utf-8').rstrip() + '\n' + ARTIFACT, encoding='utf-8')
print('Prepared delivery and artifact changes in five working copies; nothing published.')
