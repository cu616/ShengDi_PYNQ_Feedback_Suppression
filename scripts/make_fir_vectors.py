"""Deterministic full-width RTL oracle from Python integer reference."""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from feedback.cancellation import cancel_fixed

root = Path(__file__).resolve().parents[1] / 'tmp/fir_vectors'
root.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(20261018)
taps, frames = 256, 768

def write(name, values, width=24):
    (root/name).write_text(''.join(format(int(x) & ((1<<width)-1), '0%dx' % ((width+3)//4))+'\n' for x in values))

for case in range(3):
    h = np.zeros(taps, dtype=np.int64)
    if case == 0:
        h[:3] = [2**19, -2**18, 1]  # hand-checkable half, quarter, one Q20 LSB
    elif case == 1:
        h = rng.integers(-2**20, 2**20, taps, dtype=np.int64)
    else:
        h[:] = 2**23-1  # accumulate far beyond 48-bit range
    u = rng.integers(-2**23, 2**23, frames, dtype=np.int64)
    mic = rng.integers(-2**23, 2**23, frames, dtype=np.int64)
    u[:6] = [1,-1,2**23-1,-2**23,0,3]
    if case == 2: u[:] = 2**23-1
    bypass = np.arange(frames) % 11 == 0
    pred, residual, rsat = cancel_fixed(u, mic, h, bypass)
    # Independent exact convolution using object ints for prediction clipping flags.
    wide = np.convolve(u.astype(object), np.r_[0, h].astype(object))[:frames]
    rounded = [(-1 if a<0 else 1)*((abs(int(a))+2**19)//2**20) for a in wide]
    psat = [(v < -2**23 or v > 2**23-1) for v in rounded]
    for name, values in [('h',h),('u',u),('mic',mic),('pred',pred),('res',residual)]:
        write('%s%d.mem' % (name,case),values)
    write('flags%d.mem'%case, [int(b)*4+int(p)*2+int(r) for b,p,r in zip(bypass,psat,rsat)],4)
print('FIR_VECTORS_READY',root, 'cases=3 frames_each=768 taps=256')
