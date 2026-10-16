"""`python -m papertrail ...` is the same as the `papertrail` command."""
from papertrail.pipeline import main

raise SystemExit(main())
