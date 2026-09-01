"""Audit log tests: chain integrity, tamper detection, tail."""

import json

from mysti.security.audit import AuditLog


def test_log_appends_and_verifies(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.log("memory.store", "r1")
    log.log("memory.retrieve", "r1", status="failed", reason="missing")
    log.log("memory.delete", "r2", metadata={"category": "personal"})
    assert log.verify() is True
    entries = log.tail()
    assert [e["seq"] for e in entries] == [1, 2, 3]
    assert entries[1]["status"] == "failed"


def test_chain_links_entries(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.log("a", "r1")
    log.log("b", "r2")
    entries = log.tail()
    assert entries[1]["prev_hash"] == entries[0]["hash"]


def test_verify_detects_tampering(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.log("memory.store", "r1")
    log.log("memory.store", "r2")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0]["action"] = "tampered"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    assert AuditLog(path).verify() is False


def test_verify_detects_deleted_entry(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.log("a", "r1")
    log.log("b", "r2")
    lines = path.read_text().splitlines()
    # Removing a middle/first entry breaks seq numbering and hash chaining.
    path.write_text(lines[1] + "\n")
    assert AuditLog(path).verify() is False


def test_tail_truncation_cannot_be_detected_by_chain(tmp_path):
    # Documented limitation: dropping the *last* entry leaves the remaining
    # chain valid. Bucket versioning / external anchoring covers this later.
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.log("a", "r1")
    log.log("b", "r2")
    lines = path.read_text().splitlines()
    path.write_text(lines[0] + "\n")
    assert AuditLog(path).verify() is True


def test_continues_chain_after_reload(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = AuditLog(path)
    first.log("a", "r1")
    second = AuditLog(path)
    second.log("b", "r2")
    assert AuditLog(path).verify() is True
    assert len(AuditLog(path).tail()) == 2


def test_empty_log_verifies(tmp_path):
    assert AuditLog(tmp_path / "audit.jsonl").verify() is True
    assert AuditLog(tmp_path / "audit.jsonl").tail() == []
