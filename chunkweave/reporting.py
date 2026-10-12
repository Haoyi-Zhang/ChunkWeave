"""Display measured resources without inventing unavailable observations."""
from math import isfinite


def peak_rss_tex(kib: int | float | None) -> str:
    if kib is None:
        return 'not measured'
    if isinstance(kib, bool) or not isinstance(kib, (int, float)) or kib < 0:
        raise ValueError('Peak RSS must be a nonnegative finite number or null')
    try:
        mib = kib / 1024
    except OverflowError as error:
        raise ValueError('Peak RSS is outside the numeric reporting range') from error
    if not isfinite(mib):
        raise ValueError('Peak RSS must be finite')
    return f'{mib:.2f}~MiB'
