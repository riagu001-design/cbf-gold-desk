"""The only bridge from strategy engines to the CrownBearer Neural Brain (scan/brain/core.py).
Engines are intelligence providers: they PROPOSE setups and REPORT exits; the brain decides and publishes."""
import time
from brain.core import submit, close


def propose(strategy, side, entry, stop, exit_rule, note=None, target=None):
    d = submit(dict(strategy=strategy, side=side, entry=float(entry), stop=float(stop), exit_rule=exit_rule, ts=time.time(), note=note, target=target))
    tg = f", Telegram {d['telegram']}" if d.get('telegram') else ''
    return d, f"brain {d['verdict']} score {d.get('score')} id {d.get('id')}{tg}" + (f" ({'; '.join(d['reasons'])})" if d.get('reasons') else '')


def finish(pos, exit_price, how, when):
    if not pos.get('brain_id'): return 'no brain id'
    o = close(pos['brain_id'], float(exit_price), how, when.timestamp())
    if o is None: return 'already closed in brain'
    return f"brain outcome {o['R']:+.2f}R" + (f", Telegram {o['telegram']}" if o.get('telegram') else ' (not sent: was not an approved signal)')
