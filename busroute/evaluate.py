"""Score the validator against the separate ground-truth file (never used as an input feature)."""
from __future__ import annotations

import pandas as pd

from .validate import ISSUE_MAP


def score(violations: pd.DataFrame, gt: pd.DataFrame) -> dict:
    det = violations[violations.check.isin(ISSUE_MAP)].copy()
    det["issue_type"] = det.check.map(ISSUE_MAP)
    detected = set(zip(det.issue_type, det.entity_id))
    truth = set(zip(gt.issue_type, gt.entity_id))
    per = {}
    for t in sorted(set(gt.issue_type) | set(det.issue_type)):
        d, g = {e for i, e in detected if i == t}, {e for i, e in truth if i == t}
        tp = len(d & g)
        per[t] = dict(injected=len(g), detected=len(d), true_positive=tp, false_positive=len(d - g), false_negative=len(g - d),
                      precision=round(tp / len(d), 4) if d else None, recall=round(tp / len(g), 4) if g else None)
    return dict(per_issue_type=per, unexplained_violations=int((~violations.check.isin(ISSUE_MAP)).sum()),
                exact_match=detected == truth and not (~violations.check.isin(ISSUE_MAP)).any())
