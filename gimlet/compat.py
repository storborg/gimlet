from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys


PY3 = sys.version_info[0] > 2


def to_native_str(s):
    """
    Make sure this string-like thing is a native str. If it's bytes, decode it,
    but only allow ascii characters.
    """
    if not isinstance(s, str):
        return s.decode('ascii', 'strict')
    return s
