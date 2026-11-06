"""Validate content/ and print a coverage table (design §8).

    python -m content.validate            # errors fail, warnings are listed
    python -m content.validate --strict   # warnings fail too
    python -m content.validate --mvp      # also fail below the MVP coverage target
"""

import sys

from app.content.loader import main

if __name__ == "__main__":
    sys.exit(main())
