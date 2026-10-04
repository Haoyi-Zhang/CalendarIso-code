"""Write the two manuscript runtime tables to stdout from checked summary data.

Run runtime_summary.py --replay-all first when producing a new evidence set.
This exporter formats observations; it does not certify them independently.
"""
from pathlib import Path
import argparse
import json


def render(summary: dict) -> str:
    groups = summary['groups']
    lines = [r'\begin{table}[t]',
        r'\caption{Continuous execution at batch length four. Each row aggregates 120 runs. Viol. counts violating runs; idle counts avoidable core slots.}',
        r'\label{tab:runtime}', r'\centering', r'\begin{tabular}{lrrrr}',
        r'\toprule', r'Policy & Viol. & Work & Backlog & Idle \\', r'\midrule']
    for key, label in [('reservation','Reservation'),('urgent','Urgent-first'),
                       ('naive','Naive'),('snapshot','Snapshot-only'),
                       ('certified','Certified'),('certified-interrupt','Interruptible')]:
        row = groups[key+':4']
        if row['runs'] != 120:
            raise ValueError('table caption requires exactly 120 runs per group')
        values = [row[c] for c in ('violating_runs','actual_work','final_backlog','avoidable_idle_core_slots')]
        lines.append(label+' & '+' & '.join(f'{v:,}' for v in values)+r' \\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}', r'\begin{table}[t]',
        r'\caption{Batch sensitivity over the same 120 inputs. C is immutable certification; I adds readiness-triggered interruption. Proposal calls are not CPU timings.}',
        r'\label{tab:batch-runtime}', r'\centering', r'\begin{tabular}{rrrrrr}',
        r'\toprule', r'Batch & C work & C idle & I work & C calls & I calls \\', r'\midrule']
    for batch in (1,2,4,8):
        c, i = groups[f'certified:{batch}'], groups[f'certified-interrupt:{batch}']
        if c['runs'] != 120 or i['runs'] != 120:
            raise ValueError('table caption requires exactly 120 runs per group')
        values = [batch,c['actual_work'],c['avoidable_idle_core_slots'],i['actual_work'],c['proposal_calls'],i['proposal_calls']]
        lines.append(' & '.join(f'{v:,}' for v in values)+r' \\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    return '\n'.join(lines)+'\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path,
                        default=Path(__file__).resolve().parent/'results/runtime/summary.json')
    args = parser.parse_args()
    print(render(json.loads(args.summary.read_text(encoding='utf-8'))), end='')


if __name__ == '__main__':
    main()
