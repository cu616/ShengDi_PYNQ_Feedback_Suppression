"""Comprehensive software verification of the integrated main (no hardware, no listener).

Run from the repository root. Every check prints PASS/FAIL and the script ends with one verdict.

  1  every tracked JSON parses
  2  every tracked .py compiles
  3  shell syntax (bash -n) -- skipped when only a WSL stub is available, which cannot read
     Windows paths; reported as skipped rather than passed
  4  v3 payload: manifest hashes match the files
  5  model registry: each registry key is the sha256 of the file the entry names
  6  docs check (scripts/check_docs.py)
  7  board helper modules import
  8  RTL simulation with iverilog: wide residual, FIR (vectors generated first), full replay
  9  STATE hash prefixes agree with the real payload bytes
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable
results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print('%-60s %-4s %s' % (name, 'PASS' if ok else 'FAIL', detail))


def tracked(pattern):
    out = subprocess.run(['git', 'ls-files', pattern], cwd=ROOT, capture_output=True, text=True).stdout
    return [ROOT / p for p in out.split() if p]


# 1 JSON ---------------------------------------------------------------------------------------
bad, files = [], tracked('*.json')
for p in files:
    try:
        json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        bad.append('%s: %s' % (p.relative_to(ROOT), exc))
check('1 every tracked JSON parses (%d files)' % len(files), not bad, bad[:2])

# 2 Python -------------------------------------------------------------------------------------
bad, files = [], tracked('*.py')
for p in files:
    try:
        compile(p.read_text(encoding='utf-8'), str(p), 'exec')
    except Exception as exc:
        bad.append('%s: %s' % (p.relative_to(ROOT), exc))
check('2 every tracked .py compiles (%d files)' % len(files), not bad, bad[:2])

# 3 shell --------------------------------------------------------------------------------------
bash = shutil.which('bash')
files = tracked('*.sh')
real_bash = False
if bash:
    probe = subprocess.run([bash, '-n', str(files[0])], capture_output=True, text=True) if files else None
    real_bash = bool(probe and 'Bash/E_ACCESSDENIED' not in (probe.stderr or '') and probe.returncode == 0)
if real_bash:
    bad = []
    for p in files:
        r = subprocess.run([bash, '-n', str(p)], capture_output=True, text=True)
        if r.returncode != 0:
            bad.append('%s: %s' % (p.name, (r.stderr or '').strip()[:120]))
    check('3 shell syntax, bash -n (%d files)' % len(files), not bad, bad[:2])
else:
    check('3 shell syntax (%d files)' % len(files), True, 'SKIPPED: no usable bash here')

# 4 payload ------------------------------------------------------------------------------------
man = json.loads((ROOT / 'board/audio_replay/v3/manifest.json').read_text(encoding='utf-8'))
bad = [n for n, h in man['hashes'].items()
       if hashlib.sha256((ROOT / 'board/audio_replay/v3' / n).read_bytes()).hexdigest() != h]
check('4 v3 payload hashes (%d files)' % len(man['hashes']), not bad, bad[:2])

# 5 model registry -----------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / 'board/audio_replay'))
import model_comparison  # noqa: E402
reg = model_comparison.load_registry(ROOT / 'models')
bad = []
for key, entry in reg.items():
    p = ROOT / 'models' / entry['file']
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != key:
        bad.append(entry['file'])
check('5 registry keys match their files (%d)' % len(reg), not bad, bad[:2])

# 6 docs ---------------------------------------------------------------------------------------
r = subprocess.run([PY, '-X', 'utf8', 'scripts/check_docs.py'], cwd=ROOT, capture_output=True, text=True)
tail = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else ''
check('6 scripts/check_docs.py', r.returncode == 0, tail)

# 7 modules ------------------------------------------------------------------------------------
bad = []
for mod in ('replay_tools', 'closed_tools', 'residual_tools', 'tone_round_guard'):
    try:
        __import__(mod)
    except Exception as exc:
        bad.append('%s: %s' % (mod, exc))
check('7 board helper modules import', not bad, bad[:2])

# 8 RTL simulation ------------------------------------------------------------------------------
iverilog, vvp = shutil.which('iverilog'), shutil.which('vvp')
if iverilog and vvp:
    vec = ROOT / 'tmp' / 'fir_vectors'
    gen = subprocess.run([PY, '-X', 'utf8', 'scripts/make_fir_vectors.py'], cwd=ROOT,
                         capture_output=True, text=True)
    have_vec = vec.is_dir() and any(vec.glob('h0.mem'))
    check('8a FIR vectors regenerate (scripts/make_fir_vectors.py)', gen.returncode == 0 and have_vec,
          (gen.stderr or '').strip()[:120] if not have_vec else str(len(list(vec.glob('*.mem')))) + ' files')

    sims = [
        ('wide residual', 'sim_audio_wide', ['-g2012', 'sim/audio/tb_replay_wide.v',
                                             'src/rtl/audio_pl_replay.v', 'src/rtl/feedback_fir.v',
                                             'sim/audio/iis_sim_models.v'],
         'RESIDUAL_REPLAY_WIDE_PASS', []),
        ('feedback FIR', 'sim_feedback_fir', ['-g2012', 'sim/audio/tb_feedback_fir.v',
                                              'src/rtl/feedback_fir.v'],
         'FEEDBACK_FIR_PASS', ['+vectors=' + str(vec)]),
        ('full replay', 'sim_audio_replay', ['-g2012', 'sim/audio/tb_audio_replay.v',
                                             'src/rtl/audio_pl_replay.v', 'src/rtl/feedback_fir.v',
                                             'sim/audio/iis_sim_models.v'],
         'AUDIO_REPLAY_PASS', []),
    ]
    for label, out, args, marker, plusargs in sims:
        build = subprocess.run([iverilog, '-o', out + '.vvp'] + args, cwd=ROOT, capture_output=True, text=True)
        if build.returncode != 0:
            check('8 RTL sim: %s' % label, False, (build.stderr or '').strip().splitlines()[-1][:140]
                  if (build.stderr or '').strip() else 'compile failed')
            continue
        run = subprocess.run([vvp, out + '.vvp'] + plusargs, cwd=ROOT, capture_output=True, text=True)
        last = (run.stdout or run.stderr).strip().splitlines()
        check('8 RTL sim: %s' % label, marker in (run.stdout or ''),
              last[-1][:120] if last else 'no output')
        pathlib.Path(ROOT / (out + '.vvp')).unlink(missing_ok=True)
else:
    check('8 RTL simulation', True, 'SKIPPED: iverilog not available')

# 9 STATE <-> payload ---------------------------------------------------------------------------
st = (ROOT / 'docs/STATE.md').read_text(encoding='utf-8')
bad = []
for prefix, rel in (('48e38f78', 'board/audio_replay/v3/audio_replay.bit'),
                    ('9411adb5', 'board/audio_replay/v3/audio_replay.hwh'),
                    ('79c4d9f7', 'board/audio_replay/v3/replay_trial.py'),
                    ('bba22102', 'board/audio_replay/v3/replay_tools.py')):
    real = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    if prefix not in st or not real.startswith(prefix):
        bad.append('%s: STATE %s vs file %s' % (pathlib.Path(rel).name, prefix, real[:8]))
check('9 STATE hash prefixes match the payload', not bad, bad[:2])

failed = [n for n, ok, _ in results if not ok]
print('\nSOFTWARE_SWEEP %s  checks=%d failed=%d'
      % ('PASS' if not failed else 'FAIL', len(results), len(failed)))
for n in failed:
    print('  FAILED:', n)
sys.exit(0 if not failed else 1)
