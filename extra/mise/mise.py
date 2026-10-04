#!/usr/bin/env python3
import sys

from miselib.common import Error
from miselib.transpile import main

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Error as e:
        print("mise: error: %s" % e, file=sys.stderr)
        sys.exit(1)
