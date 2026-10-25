"""Poll the board's session state file (unbuffered) and optionally write an answer."""
import json
import os
import sys

sys.path.insert(0, r'D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\tmp\ssh-deps')
import paramiko  # noqa: E402

KEEP = r'D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\tmp\board-known-hosts'
client = paramiko.SSHClient()
client.load_host_keys(KEEP)
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect('192.168.2.99', username='xilinx',
               password=os.environ['SHENGDI_SSH_PASSWORD'],
               look_for_keys=False, allow_agent=False, timeout=10)
command = "cat /home/xilinx/session_state.json 2>/dev/null || echo '{}'"
_, out, _ = client.exec_command(command, timeout=20)
print(out.read().decode().strip())
client.close()
