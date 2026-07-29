# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Allow ``python -m samsarix_analytics`` to run the CLI."""

from .cli import main

raise SystemExit(main())
