"""Live product-panel run monitor for the a06 screen recording.

Connects to the board, runs a small read-only monitor there, and streams a clean status view to
this console. No hardware access, no playback: it only reads the product's own status/run files.
"""
import json
import os
import sys
import time
from pathlib import Path

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
print(' 产品面板运行记录  ·  只读监视  ', flush=True)
print('=' * 64, flush=True)

last = None
started = None
last_run_file = None
while True:
    st = status()
    state = st.get('state')
    now = time.time()
    if state == 'running' and started is None:
        started = now
    if state != 'running' and started is not None:
        pass
    line = None
    if state == 'running' and started is not None:
        line = '状态 running    已运行 %6.1f s' % (now - started)
    else:
        line = '状态 %-10s' % str(state)
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
            print(' 运行结束记录', flush=True)
            print('   请求时长     60 s', flush=True)
            print('   完成帧数     %s' % fmt(frames), flush=True)
            print('   实际时长     %s s' % ('%.2f' % secs if secs else '?'), flush=True)
            print('   结束原因     %s' % d.get('stop_reason'), flush=True)
            print('   增益饱和     %s' % d.get('gain_saturations'), flush=True)
            print('   麦克风满量程 %s' % ('是' if d.get('input_full_scale_seen') else '否'), flush=True)
            if lv:
                print('   尾窗电平     mic_rms %.1f dBFS / mic_peak %.1f dBFS' % lv, flush=True)
            print('-' * 64, flush=True)
            last_run_file = rf
        except Exception as exc:
            print('读取运行记录失败: %s' % exc, flush=True)
            last_run_file = rf
    time.sleep(0.5)
'''


def main():
    client = paramiko.SSHClient()
    client.load_host_keys(KNOWN)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(HOST, username='xilinx', password=os.environ['SHENGDI_SSH_PASSWORD'],
                   look_for_keys=False, allow_agent=False, timeout=10)
    sftp = client.open_sftp()
    with sftp.open(REMOTE, 'w') as stream:
        stream.write(MONITOR)
    sftp.chmod(REMOTE, 0o644)
    sftp.close()
    command = ("sudo -S -p '' /usr/local/share/pynq-venv/bin/python -u " + REMOTE)
    stdin, out, err = client.exec_command(command)
    stdin.write((os.environ['SHENGDI_SSH_PASSWORD'] + '\n').encode())
    stdin.flush()
    try:
        for chunk in iter(lambda: out.channel.recv(4096), b''):
            sys.stdout.write(chunk.decode('utf8', 'replace'))
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
