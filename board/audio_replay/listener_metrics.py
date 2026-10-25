"""Project listener WAV measurements, using only Python's standard library.

The total-to-background ratio retains the existing snr_db definition. Speech
change uses background power subtraction; neither value is calibrated SPL.
"""
from array import array
import hashlib
import math
from pathlib import Path
import sys
import wave


def listener_metrics(folder, confirmation):
    if confirmation != 'FIXED_SOURCE_FIXED_GAIN_NO_AGC':
        return dict(status='not_tested', reason='fixed_source_and_measurement_gain_not_confirmed')
    levels = {}; rates = set(); durations = set(); hashes = {}
    try:
        for mode in ('off', 'on'):
            for kind in ('speech', 'noise'):
                key = mode+'-'+kind; path = Path(folder)/(key+'.wav')
                with wave.open(str(path), 'rb') as stream:
                    if stream.getnchannels()!=1 or stream.getsampwidth()!=2 or stream.getcomptype()!='NONE':
                        raise ValueError('mono uncompressed PCM16 required: '+key)
                    rate = stream.getframerate(); rates.add(rate)
                    frames = stream.getnframes(); data = stream.readframes(frames)
                    if len(data)!=2*frames:
                        raise ValueError('truncated listener recording: '+key)
                x = array('h'); x.frombytes(data)
                if sys.byteorder!='little': x.byteswap()
                if len(x)<rate or any(v<=-32768 or v>=32767 for v in x):
                    raise ValueError('short or clipped listener recording: '+key)
                if kind=='speech': durations.add((len(x), rate))
                mean = math.fsum(x)/len(x)
                levels[key] = math.fsum((v-mean)**2 for v in x)/(len(x)*32768**2)
                hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        if len(rates)!=1 or len(durations)!=1:
            raise ValueError('listener rates/durations differ')
        speech = {m:levels[m+'-speech']-levels[m+'-noise'] for m in ('off','on')}
        snr = {m:10*math.log10(levels[m+'-speech']/max(levels[m+'-noise'],1e-24))
               if levels[m+'-speech']>0 else -math.inf for m in speech}
        if any(speech[m]<=0 or snr[m]<6 for m in speech):
            raise ValueError('speech power not separated from background by 6 dB')
        return dict(status='passed',
                    relative_speech_change_db=10*math.log10(speech['on']/speech['off']),
                    snr_db=snr, input_sha256=hashes, absolute_spl=None,
                    scope='fixed listener, source and recorder gain; descriptive relative result, no universal quality pass')
    except (OSError, ValueError, EOFError, wave.Error) as exc:
        return dict(status='not_tested' if isinstance(exc,FileNotFoundError) else 'failed',
                    reason=str(exc),absolute_spl=None)
