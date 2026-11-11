"""Real Hermes CLI onboarding/failure checks; real Gate, isolated profile, no model."""
import json, os, pathlib, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_integration import Integration

source = pathlib.Path(__file__).resolve().parents[1]
fixture = Integration()
fixture.setUp()
try:
    home = fixture.root / 'consumer-profile'
    home.mkdir()
    shutil.copytree(source, home / 'plugins/gate', ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__'))
    config = home / 'config.yaml'
    config.write_text('plugins:\n  enabled: [gate]\n')
    env = os.environ.copy()
    env['HERMES_HOME'] = str(home)
    env.pop('GATE_URL', None)
    env.pop('GATE_TOKEN', None)
    def credentials(url=None, token=None):
        (home / '.env').write_text(('GATE_URL='+url+'\n' if url else '') + ('GATE_TOKEN='+token+'\n' if token else ''))
    def cli(args, expected, code=0):
        result = subprocess.run([sys.executable, '-m', 'hermes_cli.main', 'gate', *args], env=env, text=True, capture_output=True, timeout=30)
        output = result.stdout + result.stderr
        assert result.returncode == code, (args, result.returncode, output)
        assert expected in " ".join(output.split()), (args, output)
        assert 'Traceback' not in output, output
        assert fixture.token not in output, 'Credential disclosure'
        print('PASS:', ' '.join(args), expected, flush=True)
        return output
    credentials()
    cli(['status'], 'Configuration missing or invalid', 1)
    credentials('http://example.invalid', 'synthetic')
    cli(['status'], 'Configuration missing or invalid', 1)
    credentials(fixture.url, 'invalid-synthetic-token')
    cli(['status'], 'Authentication rejected', 1)
    credentials('http://127.0.0.1:1', 'synthetic')
    cli(['status'], 'Connection unavailable', 1)
    cli(['resume', 'a'*24], 'Cannot resume:', 1)
    credentials(fixture.url, fixture.token)
    cli(['status'], 'First gateway setup:')
    report = json.loads(cli(['status', '--json'], 'agent:hermes-test'))
    assert report['identity'] == 'agent:hermes-test'
    config.write_text('plugins:\n  enabled: [gate]\ngateway:\n  platforms:\n    gate:\n      enabled: false\n')
    cli(['status'], 'Task pickup: disabled')
    cli(['resume', '--help'], 'Previous actions are not undone')
    cli(['resume', 'a'*24], 'Only an uncertain run', 1)
finally:
    fixture.tearDown()
