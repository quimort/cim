"""The asset_class codes live in three places. This test forbids them drifting.

1. ``AssetClass`` — the Python enum the valuation services dispatch on.
2. ``ASSET_CLASS_SEED`` — what the app considers the canonical rows.
3. The migration's ``_SEED`` — what actually landed in the database.

A migration may not import live model code (models drift; a migration is a fixed
historical record), so (3) necessarily repeats (2). That duplication is safe only
if something checks it, which is what this file is for: drift fails CI rather
than production, where it would surface as an instrument that cannot be valued.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

from app.models.asset_class import ASSET_CLASS_SEED
from app.models.enums import AssetClass

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "b1c4d7e29f30_add_asset_class_table_and_category.py"
)


def _load_migration() -> ModuleType:
    """Load the revision by path: `alembic/versions` is not an importable package."""
    spec = importlib.util.spec_from_file_location("_asset_class_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_enum_matches_the_seed_constant() -> None:
    assert {c.value for c in AssetClass} == {row["code"] for row in ASSET_CLASS_SEED}


def test_migration_seed_matches_the_seed_constant() -> None:
    """If these diverge, a freshly migrated database and a fresh test run disagree."""
    migration_seed = _load_migration()._SEED
    assert [dict(row) for row in migration_seed] == [dict(row) for row in ASSET_CLASS_SEED]
