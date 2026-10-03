from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STARTER = ROOT / "starter"
CORPUS_DIR = STARTER / "corpus" / "text"
MANIFEST = STARTER / "corpus" / "corpus_manifest.csv"
ADDRESSES = STARTER / "data" / "sample_addresses.csv"
SCHEMA = STARTER / "schema" / "rule_record.schema.json"
CHANGE_TESTS = STARTER / "dev" / "change_tests.json"
EXTRA_DOCS = ROOT / "extra_docs"  # documents released mid-event (the hour-16 ordinance)

WORK = ROOT / "work"
EXTRACTIONS = WORK / "extractions"
GEOCODED = WORK / "geocoded.json"
AUDIT_LOG = WORK / "audit_log.jsonl"

OUT = ROOT / "out"
RULES_OUT = OUT / "rules.json"
LOOKUPS_OUT = OUT / "lookups.json"
CHANGES_OUT = OUT / "changes.json"

SITE = ROOT / "site"
SITE_DATA = SITE / "data"

DEFAULT_AS_OF = "2026-10-01"
