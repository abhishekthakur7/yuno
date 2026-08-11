"""Shared, hand-authored fixture data for cross-module tests.

Each `yuno.modules.*` ticket that needs real (not hand-built-in-test-file)
data owns a subpackage here (e.g. `tests.fixtures.canonical`). Nothing is
re-exported at this top level on purpose: import the specific
subpackage you need (`from tests.fixtures.canonical import load_fixture`)
so an unrelated module's fixture package is never pulled in as a side
effect of importing this one.
"""

from __future__ import annotations
