"""Allow ``python -m helix_analytics`` to run the CLI."""

from .cli import main

raise SystemExit(main())
