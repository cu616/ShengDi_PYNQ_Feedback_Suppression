"""Check reported complex magnitudes against phase, respecting printed rounding.
No column is selected as ground truth. This is algebra, not a stability test.
"""
import argparse
import json
import math
from pathlib import Path

DEFAULT_ROWS = [
    (400,1.331,.994,.459,16.9), (4000,.515,.628,.262,-109.2),
    (8000,.505,.476,.372,174.5), (8350,1.276,1.079,.815,-152.),
    (8500,1.295,1.135,1.141,32.3), (9000,.320,.269,.245,-136.)]
FS=48828.125
GAIN_3DB=5786/4096


def residual(a,b,deg):
    return math.sqrt(max(0,a*a+b*b-2*a*b*math.cos(math.radians(deg))))


def check(rows):
    result=[]
    for f,a,b,r,p in rows:
        calc=residual(a,b,p)
        # Conservative error bound from complex-vector perturbations. Each printed
        # magnitude has +/-0.0005 uncertainty; printed phase has +/-0.05 degrees.
        bound=.001+(b+.0005)*2*math.sin(math.radians(.05)/2)
        c=(a*a+b*b-r*r)/(2*a*b) if a*b else None
        implied=math.degrees(math.acos(c)) if c is not None and -1<=c<=1 else None
        result.append(dict(hz=f,H_abs=a,Hh_abs=b,reported_residual=r,
            reported_phase_deg=p,residual_from_reported_phase=calc,
            discrepancy=calc-r,rounding_difference_bound=bound+.0005,
            consistent_with_printed_precision=abs(calc-r)<=bound+.0005,
            implied_phase_magnitude_deg_if_magnitudes_correct=implied,
            phase_sign_and_cycle_unknown=True,
            gain3_times_reported_residual=GAIN_3DB*r,
            gain3_times_phase_derived_residual=GAIN_3DB*calc))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path)
    args=p.parse_args()
    rows=check(DEFAULT_ROWS)
    out={'source':'A forwarded table, not raw captures', 'rows':rows,
         'scalar_checks':{
           '39_4_deg_at_8350_hz_pure_delay_samples':39.4/360*FS/8350,
           '152_deg_at_8350_hz_pure_delay_samples':152/360*FS/8350,
           'gain3_q12':5786,'gain3_linear':GAIN_3DB,
           'residual_for_unity_magnitude':1/GAIN_3DB,
           'magnitude_headroom_db_at_residual_0_70':-20*math.log10(GAIN_3DB*.70),
           'residual_for_3db_magnitude_headroom':10**(-3/20)/GAIN_3DB,
           'center_db_if_beta_is_0_65_amplitude':20*math.log10(.65)},
         'interpretation':'Conditional arithmetic only. Actual complex H and Hhat required.'}
    for r in rows:
        print('%5d Hz reported %.6f calculated %.6f rounding_bound %.6f consistent=%s' %
              (r['hz'],r['reported_residual'],r['residual_from_reported_phase'],
               r['rounding_difference_bound'],r['consistent_with_printed_precision']))
    print(json.dumps(out['scalar_checks'],indent=2))
    if args.out:
        with args.out.open('x',encoding='utf-8') as stream:
            json.dump(out,stream,ensure_ascii=False,indent=2,allow_nan=False)


if __name__=='__main__':main()
