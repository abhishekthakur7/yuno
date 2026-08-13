"""Proves spec §3.2's dependency-direction/framework-free rules and spec
§3.3's module-independence rule are enforced automatically (SYS-01/NFR-07).

The contracts live in `[tool.importlinter]` in `pyproject.toml`. This
module runs them through import-linter's Python API rather than shelling
out to the `lint-imports` CLI, which is just a thin wrapper around the
same functions.

Beyond running the contracts against real code:

1. Nothing in `yuno` currently crosses these boundaries the wrong way, so a
   clean run alone can't distinguish a correctly-configured contract from
   a silently-toothless one (e.g. a typo'd module name). The self-tests
   below build tiny, deliberately-violating import graphs in memory
   (`grimp.ImportGraph`, unrelated to `yuno`) and run the *exact*
   `LayersContract`/`ForbiddenContract`/`IndependenceContract` classes
   against them.
2. import-linter only sees `import`/`from` statements. Raw FTS5 SQL syntax
   (`MATCH`, `fts5`) embedded in a string literal is invisible to it, so a
   separate string-level test greps every framework-free source file for
   both that and `subprocess` usage.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from grimp import ImportGraph
from importlinter import configuration
from importlinter.application.use_cases import create_report, read_user_options
from importlinter.contracts.forbidden import ForbiddenContract
from importlinter.contracts.independence import IndependenceContract
from importlinter.contracts.layers import LayersContract
from importlinter.domain.contract import registry

SERVER_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = SERVER_ROOT / "pyproject.toml"
SRC_ROOT = SERVER_ROOT / "src" / "yuno"

EXPECTED_ROOT_LAYERS_CONTRACT_NAME = (
    "Composition-root layering: api > modules > shared (spec §3.2)"
)
EXPECTED_MODULE_LAYERS_CONTRACT_NAME = "Per-module layering (spec §3.3)"
EXPECTED_FORBIDDEN_CONTRACT_NAME = (
    "Domain and application are framework-free (spec §3.2, SYS-01/NFR-07)"
)
EXPECTED_INDEPENDENCE_CONTRACT_NAME = "Module independence (spec §3.3, IDK-102 scope)"

EXPECTED_ROOT_LAYERS = ["yuno.api", "yuno.modules", "yuno.shared"]
EXPECTED_MODULE_CONTAINERS = [
    "yuno.modules.identity",
    "yuno.modules.audit",
    "yuno.modules.canonical",
    "yuno.modules.profiles_goals",
    "yuno.modules.diagnostics",
    "yuno.modules.evidence_evaluation",
    "yuno.modules.learning_content",
    "yuno.modules.roadmap",
    "yuno.modules.imports",
    "yuno.modules.interview",
    "yuno.modules.jobs_events",
    "yuno.modules.notebook_review",
    "yuno.modules.provenance",
    "yuno.modules.settings_data",
    "yuno.modules.provider",
    "yuno.modules.hands_on",
    "yuno.modules.runner",
    "yuno.modules.search",
    "yuno.modules.data_lifecycle",
]
EXPECTED_MODULE_LAYERS = ["(service)", "(repository)", "models", "ports", "domain"]
EXPECTED_FORBIDDEN_MODULES = {
    "fastapi",
    "starlette",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "subprocess",
}
EXPECTED_FORBIDDEN_SOURCE_MODULES = {
    "yuno.shared.domain",
    "yuno.shared.application",
    "yuno.modules.identity.domain",
    "yuno.modules.identity.ports",
    "yuno.modules.identity.service",
    "yuno.modules.audit.domain",
    "yuno.modules.audit.ports",
    "yuno.modules.canonical.domain",
    "yuno.modules.canonical.ports",
    "yuno.modules.canonical.validation",
    "yuno.modules.profiles_goals.domain",
    "yuno.modules.profiles_goals.ports",
    "yuno.modules.profiles_goals.service",
    "yuno.modules.diagnostics.domain",
    "yuno.modules.diagnostics.ports",
    "yuno.modules.diagnostics.service",
    "yuno.modules.evidence_evaluation.domain",
    "yuno.modules.learning_content.domain",
    "yuno.modules.learning_content.ports",
    "yuno.modules.learning_content.service",
    "yuno.modules.roadmap.domain",
    "yuno.modules.roadmap.ports",
    "yuno.modules.roadmap.service",
    "yuno.modules.imports.domain",
    "yuno.modules.imports.ports",
    "yuno.modules.imports.service",
    "yuno.modules.interview.domain",
    "yuno.modules.interview.ports",
    "yuno.modules.interview.service",
    "yuno.modules.jobs_events.domain",
    "yuno.modules.jobs_events.ports",
    "yuno.modules.notebook_review.domain",
    "yuno.modules.notebook_review.ports",
    "yuno.modules.notebook_review.service",
    "yuno.modules.provenance.domain",
    "yuno.modules.provenance.ports",
    "yuno.modules.settings_data.domain",
    "yuno.modules.settings_data.ports",
    "yuno.modules.settings_data.service",
    "yuno.modules.provider.domain",
    "yuno.modules.provider.ports",
    "yuno.modules.provider.service",
    "yuno.modules.hands_on.domain",
    "yuno.modules.hands_on.ports",
    "yuno.modules.hands_on.service",
    "yuno.modules.runner.domain",
    "yuno.modules.runner.ports",
    "yuno.modules.search.domain",
    "yuno.modules.search.ports",
    "yuno.modules.data_lifecycle.domain",
    "yuno.modules.data_lifecycle.ports",
    "yuno.modules.data_lifecycle.service",
}
EXPECTED_INDEPENDENCE_MODULES = {
    "yuno.modules.identity",
    "yuno.modules.audit",
    "yuno.modules.canonical",
    "yuno.modules.profiles_goals",
    "yuno.modules.diagnostics",
    "yuno.modules.evidence_evaluation",
    "yuno.modules.learning_content",
    "yuno.modules.roadmap",
    "yuno.modules.imports",
    "yuno.modules.interview",
    "yuno.modules.jobs_events",
    "yuno.modules.notebook_review",
    "yuno.modules.provenance",
    "yuno.modules.settings_data",
    "yuno.modules.provider",
    "yuno.modules.hands_on",
    "yuno.modules.runner",
    "yuno.modules.search",
    "yuno.modules.data_lifecycle",
}

# Using import-linter's Python API directly (rather than the `lint-imports`
# CLI) means doing two bits of bootstrapping the CLI normally does for us:
#
# 1. `configuration.configure()` wires up the `settings` singleton (cache
#    dir, TOML/INI readers, timer, graph builder) that `read_user_options`/
#    `create_report`/`ForbiddenContract.check` all reach into. Skipping it
#    raises `KeyError` from `app_config.settings.__getattr__` deep inside
#    import-linter, not a clean local error, the first time any of them run.
# 2. The contract-type registry is populated by the CLI's private
#    `_register_contract_types`, not merely by importing the library, so we
#    register the three built-in types `pyproject.toml` uses ourselves via
#    the public `importlinter.domain.contract.registry`.
#
# Both are done once at import time; both are idempotent to repeat.
configuration.configure()
registry.register(LayersContract, "layers")
registry.register(ForbiddenContract, "forbidden")
registry.register(IndependenceContract, "independence")


@pytest.fixture(scope="module")
def user_options():
    return read_user_options(config_filename=str(PYPROJECT))


# ---------------------------------------------------------------------------
# Configuration sanity: the contracts we rely on are actually declared.
# Catches a typo'd/missing contract in pyproject.toml; the self-tests below
# catch the contract mechanism itself silently not working.
# ---------------------------------------------------------------------------


def test_pyproject_declares_the_required_contracts(user_options):
    assert user_options.session_options["root_packages"] == ["yuno"]
    assert user_options.session_options.get("include_external_packages") == "True", (
        "forbidden_modules below are all external to 'yuno'; without this flag "
        "ForbiddenContract.check() raises instead of reporting a clean pass/fail"
    )
    assert user_options.contracts_options, (
        "pyproject.toml declares no import-linter contracts"
    )

    by_name = {c["name"]: c for c in user_options.contracts_options}

    root_layers_contract = by_name[EXPECTED_ROOT_LAYERS_CONTRACT_NAME]
    assert root_layers_contract["type"] == "layers"
    assert root_layers_contract["layers"] == EXPECTED_ROOT_LAYERS

    module_layers_contract = by_name[EXPECTED_MODULE_LAYERS_CONTRACT_NAME]
    assert module_layers_contract["type"] == "layers"
    assert module_layers_contract["containers"] == EXPECTED_MODULE_CONTAINERS
    assert module_layers_contract["layers"] == EXPECTED_MODULE_LAYERS

    forbidden_contract = by_name[EXPECTED_FORBIDDEN_CONTRACT_NAME]
    assert forbidden_contract["type"] == "forbidden"
    assert (
        set(forbidden_contract["source_modules"]) == EXPECTED_FORBIDDEN_SOURCE_MODULES
    )
    assert set(forbidden_contract["forbidden_modules"]) == EXPECTED_FORBIDDEN_MODULES

    independence_contract = by_name[EXPECTED_INDEPENDENCE_CONTRACT_NAME]
    assert independence_contract["type"] == "independence"
    assert set(independence_contract["modules"]) == EXPECTED_INDEPENDENCE_MODULES
    # See pyproject.toml's comment on this contract for why these edges
    # are legitimate.
    assert set(independence_contract["ignore_imports"]) == {
        "yuno.modules.jobs_events.service -> yuno.modules.audit.**",
        "yuno.modules.identity.service -> yuno.modules.audit.**",
        "yuno.modules.canonical.publisher -> yuno.modules.identity.**",
        "yuno.modules.canonical.publisher -> yuno.modules.audit.**",
        "yuno.modules.profiles_goals.ports -> yuno.modules.audit.**",
        "yuno.modules.profiles_goals.service -> yuno.modules.audit.**",
        "yuno.modules.diagnostics.ports -> yuno.modules.audit.**",
        "yuno.modules.diagnostics.service -> yuno.modules.audit.**",
        "yuno.modules.evidence_evaluation.ports -> yuno.modules.audit.**",
        "yuno.modules.evidence_evaluation.service -> yuno.modules.audit.**",
        "yuno.modules.roadmap.ports -> yuno.modules.audit.**",
        "yuno.modules.roadmap.service -> yuno.modules.audit.**",
        "yuno.modules.imports.ports -> yuno.modules.audit.**",
        "yuno.modules.imports.service -> yuno.modules.audit.**",
        "yuno.modules.notebook_review.ports -> yuno.modules.audit.**",
        "yuno.modules.notebook_review.service -> yuno.modules.audit.**",
        "yuno.modules.settings_data.ports -> yuno.modules.audit.**",
        "yuno.modules.settings_data.service -> yuno.modules.audit.**",
        "yuno.modules.provider.service -> yuno.modules.audit.**",
        "yuno.modules.hands_on.service -> yuno.modules.evidence_evaluation.**",
        "yuno.modules.profiles_goals.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.diagnostics.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.learning_content.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.roadmap.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.imports.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.interview.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.notebook_review.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.evidence_evaluation.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.jobs_events.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.jobs_events.models -> yuno.modules.data_lifecycle.**",
        "yuno.modules.settings_data.repository -> yuno.modules.data_lifecycle.**",
        "yuno.modules.data_lifecycle.repository -> yuno.modules.diagnostics.**",
        "yuno.modules.data_lifecycle.repository -> yuno.modules.interview.**",
        "yuno.modules.data_lifecycle.repository -> yuno.modules.jobs_events.**",
        "yuno.modules.data_lifecycle.repository -> yuno.modules.runner.**",
        "yuno.modules.data_lifecycle.repository -> yuno.modules.settings_data.**",
    }


# ---------------------------------------------------------------------------
# The real check: run the configured contracts against the real codebase.
# ---------------------------------------------------------------------------


def test_import_linter_contracts_pass_against_real_code(user_options):
    report = create_report(user_options, cache_dir=None)

    if report.contains_failures:
        failures = [
            f"- {contract.name} ({contract.__class__.__name__}): {check.metadata}"
            for contract, check in report.get_contracts_and_checks()
            if not check.kept
        ]
        pytest.fail(
            "import-linter contract(s) failed:\n" + "\n".join(failures), pytrace=False
        )


# ---------------------------------------------------------------------------
# Self-tests: prove the guards actually bite, independent of yuno's code.
#
# Each builds a tiny, deliberately-violating import graph in memory
# (`grimp.ImportGraph`, unrelated to `yuno`) and runs the *exact* Contract
# class our pyproject.toml references against it, so the contract set
# can't silently degrade to a no-op (e.g. an empty `layers`/`modules` list)
# without one of these tests failing.
# ---------------------------------------------------------------------------


def test_layers_contract_detects_a_reverse_layer_import():
    graph = ImportGraph()
    graph.add_module("demo")
    graph.add_module("demo.high")
    graph.add_module("demo.low")
    # A lower layer must never import a higher one.
    graph.add_import(importer="demo.low", imported="demo.high")

    contract = LayersContract(
        name="self-test layers",
        session_options={"root_packages": ["demo"]},
        contract_options={
            "name": "self-test layers",
            "type": "layers",
            "layers": ["demo.high", "demo.low"],
        },
    )
    check = contract.check(graph, verbose=False)
    assert not check.kept, (
        "LayersContract did not detect a deliberate reverse-layer import"
    )


def test_forbidden_contract_detects_a_forbidden_import():
    graph = ImportGraph()
    graph.add_module("demo")
    graph.add_module("demo.domain")
    graph.add_import(importer="demo.domain", imported="forbidden_pkg")

    contract = ForbiddenContract(
        name="self-test forbidden",
        session_options={
            "root_packages": ["demo"],
            "include_external_packages": "True",
        },
        contract_options={
            "name": "self-test forbidden",
            "type": "forbidden",
            "source_modules": ["demo.domain"],
            "forbidden_modules": ["forbidden_pkg"],
        },
    )
    check = contract.check(graph, verbose=False)
    assert not check.kept, (
        "ForbiddenContract did not detect a deliberate forbidden import"
    )


def test_independence_contract_detects_a_cross_module_import():
    """Proves the mechanism catches a cross-module ORM/repository import
    (spec §3.2), against an in-memory graph rather than today's real
    `yuno.modules` set, whose non-cross-cutting members don't yet import
    each other.
    """
    graph = ImportGraph()
    graph.add_module("demo")
    graph.add_module("demo.modules")
    graph.add_module("demo.modules.alpha")
    graph.add_module("demo.modules.alpha.repository")
    graph.add_module("demo.modules.beta")
    graph.add_module("demo.modules.beta.repository")
    # A cross-module ORM/repository import -- exactly what spec §3.2's
    # "cross-module ORM mutation is forbidden" rules out.
    graph.add_import(
        importer="demo.modules.alpha.repository",
        imported="demo.modules.beta.repository",
    )

    contract = IndependenceContract(
        name="self-test independence",
        session_options={"root_packages": ["demo"]},
        contract_options={
            "name": "self-test independence",
            "type": "independence",
            "modules": ["demo.modules.alpha", "demo.modules.beta"],
        },
    )
    check = contract.check(graph, verbose=False)
    assert not check.kept, (
        "IndependenceContract did not detect a deliberate cross-module import"
    )


# ---------------------------------------------------------------------------
# String-level check: import-linter only sees imports, not SQL text.
#
# Patterns are deliberately narrower than a bare substring search: a plain
# `"subprocess"` match false-positives on a docstring describing this rule,
# and a case-insensitive `MATCH` false-positives on `PreconditionFailedError`'s
# docstring ("stale `If-Match`"). Both are real strings in the current
# codebase.
# ---------------------------------------------------------------------------

_SUBPROCESS_USAGE = re.compile(
    r"\bimport\s+subprocess\b"
    r"|\bfrom\s+subprocess\b"
    r"|\bsubprocess\s*\."
    r"|__import__\(\s*['\"]subprocess['\"]"
    r"|import_module\(\s*['\"]subprocess['\"]"
)
_FTS5_TOKEN = re.compile(r"\bfts5\b", re.IGNORECASE)
_FTS_MATCH_KEYWORD = re.compile(
    r"\bMATCH\b"
)  # case-sensitive: the SQL keyword, not English prose

_STRING_PATTERNS = {
    "subprocess usage": _SUBPROCESS_USAGE,
    "FTS5 virtual-table syntax": _FTS5_TOKEN,
    "FTS MATCH syntax": _FTS_MATCH_KEYWORD,
}


def _framework_free_source_files() -> list[Path]:
    """Every file the "framework-free" forbidden contract's `source_modules`
    covers: `shared/domain`/`shared/application`, plus each module's
    `domain.py`/`ports.py`/`service.py` (never `models.py`/`repository.py`,
    that module's infrastructure layer, which may import SQLAlchemy).
    """
    files: list[Path] = []
    for root in (SRC_ROOT / "shared" / "domain", SRC_ROOT / "shared" / "application"):
        files.extend(sorted(root.rglob("*.py")))

    modules_root = SRC_ROOT / "modules"
    for module_dir in sorted(p for p in modules_root.iterdir() if p.is_dir()):
        for filename in ("domain.py", "ports.py", "service.py"):
            candidate = module_dir / filename
            if candidate.exists():
                files.append(candidate)
    return files


def test_no_subprocess_or_fts_syntax_in_domain_or_application():
    """import-linter's contracts (above) catch `import subprocess`
    structurally but can't catch raw FTS5 SQL syntax embedded in a string
    literal (spec §3.2 also forbids that from domain/application), since
    it isn't a Python import. This sweeps source text for both, over every
    file the framework-free forbidden contract's `source_modules` covers.
    """
    violations: list[str] = []
    for path in _framework_free_source_files():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in _STRING_PATTERNS.items():
                if pattern.search(line):
                    rel = path.relative_to(SERVER_ROOT)
                    violations.append(
                        f"{rel}:{lineno}: forbidden {label}: {line.strip()!r}"
                    )

    assert not violations, (
        "domain/application code must not reference subprocess or raw FTS syntax (spec §3.2):\n"
        + "\n".join(violations)
    )
