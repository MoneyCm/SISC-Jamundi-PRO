"""Prepare isolated, scoped release checkouts. Does not push or deploy."""
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[2]
RELEASE = PROJECT / 'tmp/source-delivery-release'
MONITORS = {
    'monitor-policia': ('sisc_heartbeat.py', 'monitor.yml'),
    'monitor-mindefensa': ('sisc_heartbeat.py', 'monitor.yml'),
    'monitor-siedco': ('sisc_heartbeat.py', 'monitor_siedco.yml'),
    'monitor-valle': ('src/integrations/sisc_heartbeat.py', 'extract_jamundi.yml'),
    'monitor-fiscalia-spoa-v3': ('src/spoa_monitor/sisc.py', 'monitor_spoa_v3.yml'),
}

for repo, (module, workflow) in MONITORS.items():
    source = PROJECT.parent / repo
    target = RELEASE / repo
    patch = subprocess.check_output(['git', '-C', str(source), 'diff', '--binary', 'HEAD', '--', module, f'.github/workflows/{workflow}'])
    subprocess.run(['git', '-C', str(target), 'apply', '--check', '-'], input=patch, check=True)
    subprocess.run(['git', '-C', str(target), 'apply', '-'], input=patch, check=True)
    if repo != 'monitor-fiscalia-spoa-v3':
        shutil.copyfile(source / 'test_sisc_delivery.py', target / 'test_sisc_delivery.py')
    else:
        test = (PROJECT / 'backend/tests/test_fiscalia_delivery_prepared.py').read_text(encoding='utf-8')
        test = test.replace("Path(__file__).resolve().parents[3] / 'monitor-fiscalia-spoa-v3/src/spoa_monitor/sisc.py'", "Path(__file__).resolve().parents[1] / 'src/spoa_monitor/sisc.py'")
        (target / 'tests/test_sisc_delivery.py').write_text(test, encoding='utf-8')
    print(repo, 'scoped patch applied')

target = RELEASE / 'SISC-backend'
for name in ['backend/api/source_center.py', 'backend/api/fiscalia_spoa.py',
             'backend/tests/test_fiscalia_spoa_contract.py',
             'backend/scripts/sync_source_monitors.py', 'backend/scripts/start_source_sync.ps1',
             'backend/tests/test_source_monitor_sync.py']:
    destination = target / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if name == 'backend/api/source_center.py':
        patch = subprocess.check_output(['git', '-C', str(PROJECT), 'diff', '--binary', 'HEAD', '--', name])
        subprocess.run(['git', '-C', str(target), 'apply', '-'], input=patch, check=True)
    else:
        shutil.copyfile(PROJECT / name, destination)

# Only the Fiscalia connector belongs to this release, not Medicina Legal.
name = 'backend/services/source_center_service.py'
source_text = (PROJECT / name).read_text(encoding='utf-8')
block = source_text[source_text.index('    "FISCALIA_SPOA_V3": {'):source_text.index('    "MEDICINA_LEGAL": {')]
content = (target / name).read_text(encoding='utf-8')
assert '"FISCALIA_SPOA_V3": {' not in content
content = content.replace('\n}\n\nSTATUS_LABELS', '\n' + block + '}\n\nSTATUS_LABELS', 1)
anchor = '            cls._apply_state(cls._base("OBSERVATORIO_VALLE"), states.get("OBSERVATORIO_VALLE")),\n'
assert anchor in content
content = content.replace(anchor, anchor + '            cls._apply_state(cls._base("FISCALIA_SPOA_V3"), states.get("FISCALIA_SPOA_V3")),\n', 1)
(target / name).write_text(content, encoding='utf-8')

main = target / 'backend/main.py'
content = main.read_text(encoding='utf-8')
anchor = 'from api import '
lines = content.splitlines()
index = next(i for i, line in enumerate(lines) if line.startswith(anchor))
lines[index] += ', fiscalia_spoa'
content = '\n'.join(lines) + '\n'
anchor = 'app.include_router(source_center.router, prefix="/api/source-center", tags=["source-center"])'
assert anchor in content
content = content.replace(anchor, anchor + '\napp.include_router(fiscalia_spoa.router, prefix="/api/fiscalia-spoa", tags=["fiscalia-spoa"])', 1)
main.write_text(content, encoding='utf-8')

models = target / 'backend/db/models.py'
content = models.read_text(encoding='utf-8')
if 'from db.models_fiscalia_spoa import' not in content:
    anchor = '        from db.models_source_center import SourceConnectorState'
    assert anchor in content
    content = content.replace(anchor, anchor + '\n        from db.models_fiscalia_spoa import FiscaliaSpoaRun, FiscaliaSpoaSnapshot, FiscaliaSpoaRecord', 1)
    models.write_text(content, encoding='utf-8')

# The existing catalog test anticipated Medicina Legal; scope it to this release.
test = target / 'backend/tests/test_source_center_contract.py'
content = test.read_text(encoding='utf-8')
content = '\n'.join(line for line in content.splitlines() if 'MEDICINA_LEGAL' not in line) + '\n'
test.write_text(content, encoding='utf-8')

docs = target / 'docs/CENTRO_DE_FUENTES.md'
local_docs = (PROJECT / 'docs/CENTRO_DE_FUENTES.md').read_text(encoding='utf-8')
start = local_docs.index('### Sincronizacion de la instalacion local')
end = local_docs.index('\n- **Al dia**', start)
docs.write_text(docs.read_text(encoding='utf-8') + '\n\n' + local_docs[start:end].replace('`START_SISC_AUTO.bat` inicia este proceso oculto sin duplicarlo.', '`powershell -File backend/scripts/start_source_sync.ps1` inicia el proceso oculto sin duplicarlo.'), encoding='utf-8')
print('SISC-Jamundi-PRO scoped Fiscalia and local sync changes prepared')
