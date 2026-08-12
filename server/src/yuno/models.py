"""Import every module's ORM models so `Base.metadata` is complete as soon
as `yuno.models` is imported.

Composition root, not `yuno.shared`: populating one shared `Base.metadata`
requires importing every module's `models.py`, which `yuno.shared` must
never do (see `yuno.shared`'s docstring). The schema-sweep test and
Alembic autogenerate both rely on this: they import this module once and
expect `Base.metadata.tables` to already contain every table in the
system.
"""

from __future__ import annotations

from yuno.modules.audit import models as audit_models
from yuno.modules.canonical import models as canonical_models
from yuno.modules.diagnostics import models as diagnostics_models
from yuno.modules.evidence_evaluation import models as evidence_evaluation_models
from yuno.modules.identity import models as identity_models
from yuno.modules.imports import models as imports_models
from yuno.modules.interview import models as interview_models
from yuno.modules.learning_content import models as learning_content_models
from yuno.modules.notebook_review import models as notebook_review_models
from yuno.modules.profiles_goals import models as profiles_goals_models
from yuno.modules.provenance import models as provenance_models
from yuno.modules.roadmap import models as roadmap_models
from yuno.modules.settings_data import models as settings_data_models

__all__ = [
    "audit_models",
    "canonical_models",
    "diagnostics_models",
    "evidence_evaluation_models",
    "identity_models",
    "imports_models",
    "interview_models",
    "learning_content_models",
    "notebook_review_models",
    "profiles_goals_models",
    "provenance_models",
    "roadmap_models",
    "settings_data_models",
]
