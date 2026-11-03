"""Live product-panel run monitor for the a06 screen recording (ASCII output, Windows safe).

Connects to the board, runs a small read-only monitor there, and streams a clean status view to
this console. It never plays audio and never touches the hardware controls.
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / 'a06_monitor_last_run.log'

DEPS = r'D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\tmp\ssh-deps'
sys.path.insert(0, DEPS)
import paramiko  # noqa: E402

HOST = '192.168.2.99'
KNOWN = r'D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\tmp\board-known-hosts'
REMOTE = '/home/xilinx/_a06_monitor.py'

MONITOR = r'''
import glob, json, os, time
import numpy as np

STATE = '/home/xilinx/.local/state/shengdi/status.json'
RUNS = '/home/xilinx/.local/state/shengdi/runs'
RATE = 48828.125


def status():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except Exception:
        return {}


def newest_run():
    files = sorted(glob.glob(RUNS + '/*/io/*/*run*.status.json'), key=os.path.getmtime)
    return files[-1] if files else None


def tail_levels(status_file):
    npz = status_file.replace('.status.json', '.npz')
    if not os.path.exists(npz):
        return None
    try:
        with np.load(npz, allow_pickle=False) as z:
            mic = np.asarray(z['microphone'], float)
        return (20 * np.log10(max(float(np.sqrt(np.mean(mic ** 2))), 2 ** -23)),
                20 * np.log10(max(float(np.max(np.abs(mic))), 2 ** -23)))
    except Exception:
        return None


def fmt(x):
    return '{:,}'.format(int(x)) if isinstance(x, (int, float)) else str(x)


print('=' * 64, flush=True)
print(' PRODUCT RUN RECORD  (live, read-only)', flush=True)
print('=' * 64, flush=True)

last = None
started = None
last_run_file = newest_run()
while True:
    st = status()
    state = st.get('state')
    now = time.time()
    if state == 'running' and started is None:
        started = now
    if state == 'running' and started is not None:
        line = 'STATE  running      elapsed %6.1f s' % (now - started)
    else:
        line = 'STATE  %s' % str(state)
    if line != last:
        print(line, flush=True)
        last = line
    rf = newest_run()
    if state != 'running' and rf and rf != last_run_file:
        try:
            d = json.load(open(rf, encoding='utf-8'))
            frames = d.get('completed_frames')
            secs = (frames / RATE) if isinstance(frames, int) else None
            lv = tail_levels(rf)
            print('-' * 64, flush=True)
            print(' RUN FINISHED', flush=True)
            print('   requested          60 s', flush=True)
            print('   completed frames   %s' % fmt(frames), flush=True)
            print('   actual duration    %s s' % ('%.2f' % secs if secs else '?'), flush=True)
            print('   stop reason        %s' % d.get('stop_reason'), flush=True)
            print('   gain saturations   %s' % d.get('gain_saturations'), flush=True)
            print('   input full scale   %s' % ('yes' if d.get('input_full_scale_seen') else 'no'), flush=True)
            if lv:
                print('   tail mic level     rms %.1f dBFS / peak %.1f dBFS' % lv, flush=True)
            print('-' * 64, flush=True)
            last_run_file = rf
        except Exception as exc:
            print('read run record failed: %s' % exc, flush=True)
            last_run_file = rf
    time.sleep(0.5)
'''


def log(text):
    try:
        with LOG.open('a', encoding='utf-8') as stream:
            stream.write(text)
    except Exception:
        pass


def emit(text):
    sys.stdout.write(text)
    sys.stdout.flush()
    log(text)


def main():
    LOG.write_text('a06 monitor session %s\n' % time.strftime('%Y-%m-%d %H:%M:%S'),
                   encoding='utf-8')
    emit('connecting to board...\n')
    password = os.environ.get('SHENGDI_SSH_PASSWORD', 'xilinx')
    client = paramiko.SSHClient()
    client.load_host_keys(KNOWN)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(HOST, username='xilinx', password=password,
                   look_for_keys=False, allow_agent=False, timeout=10)
    sftp = client.open_sftp()
    with sftp.open(REMOTE, 'w') as stream:
        stream.write(MONITOR)
    sftp.chmod(REMOTE, 0o644)
    sftp.close()
    command = ("sudo -S -p '' /usr/local/share/pynq-venv/bin/python -u " + REMOTE)
    stdin, out, err = client.exec_command(command)
    stdin.write((password + '\n').encode())
    stdin.flush()
    try:
        for chunk in iter(lambda: out.channel.recv(4096), b''):
            emit(chunk.decode('utf8', 'replace'))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MONITOR ERROR: %r' % (exc,))
        log('MONITOR ERROR: %r\n' % (exc,))
        time.sleep(3)
