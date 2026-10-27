"""Exercise the installed entry point away from the source and personal data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


exe = Path(sys.executable).parent / ('agent-tally.exe' if os.name == 'nt' else 'agent-tally')
with tempfile.TemporaryDirectory() as folder:
    env = dict(os.environ, HOME=folder, USERPROFILE=folder, PYTHONUTF8='1')
    def run(*args, expected=0):
        result = subprocess.run([str(exe), *args], cwd=folder, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        assert result.returncode == expected, (args, result.stdout, result.stderr)
        return result.stdout
    assert 'agent-tally' in run('--help')
    assert 'agent-tally run claude' in run()
    run('run', expected=2)
    for command in ('history', 'recent', 'top', 'export'):
        assert json.loads(run(command, '--json')) == []
    assert json.loads(run('hourly', '--json'))['hourly'] == []
    data = json.loads(run('cost', 'unknown-fixture-model', '1000', '500', '--json'))
    assert data['estimated_cost_usd'] is None
    run('budget', 'set', '--daily', '-1', expected=2)
    run('config', 'set', 'fixture-model', 'input', '2')
    run('config', 'set', 'fixture-model', 'output', '8')
    run('budget', 'set', '--session', '0.001')
    fixture = Path(folder) / 'agent.py'
    fixture.write_text("import time\nprint('model: fixture-model', flush=True)\nprint('tokens_in: 1000 tokens_out: 500', flush=True)\ntime.sleep(30)\n", encoding='utf-8')
    run('run', '--tag', 'fixture', sys.executable, str(fixture), expected=137)
    rows = json.loads(run('history', '--since', 'all', '--json'))
    assert len(rows) == 1
    assert rows[0]['cost'] == 0.006
    assert rows[0]['ended_at']
    assert rows[0]['tags'] == 'fixture'
    run('budget', 'clear')
    run('run', sys.executable, '-c', 'raise SystemExit(7)', expected=7)
    run('run', 'missing-synthetic-agent-xyz', expected=127)
    rows = json.loads(run('export', '--json'))
    assert len(rows) == 3 and all(row['ended_at'] for row in rows)
print('Installed CLI consumer smoke passed (empty, unknown pricing, budget kill, repeated/error flows).')
