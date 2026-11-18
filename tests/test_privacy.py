"""Tests for privacy utilities."""
from __future__ import annotations
import pytest
from src.ueba.privacy import pseudonymize_user_id, truncate_ip, sanitize_comment


def test_pseudonymize_deterministic():
    p1 = pseudonymize_user_id("E0001", salt="test-salt")
    p2 = pseudonymize_user_id("E0001", salt="test-salt")
    assert p1 == p2


def test_pseudonymize_different_users():
    p1 = pseudonymize_user_id("E0001", salt="test-salt")
    p2 = pseudonymize_user_id("E0002", salt="test-salt")
    assert p1 != p2


def test_pseudonymize_different_salts():
    p1 = pseudonymize_user_id("E0001", salt="salt-a")
    p2 = pseudonymize_user_id("E0001", salt="salt-b")
    assert p1 != p2


def test_pseudonym_no_real_id():
    pseudonym = pseudonymize_user_id("E0001", salt="test-salt")
    assert "E0001" not in pseudonym


def test_ip_truncation():
    result = truncate_ip("192.168.1.100")
    assert result == "192.168.1.0/24"
    assert "100" not in result


def test_ip_truncation_different_values():
    r1 = truncate_ip("10.0.0.1")
    r2 = truncate_ip("10.0.0.254")
    assert r1 == r2


def test_no_full_ip_in_analytics():
    full_ip = "192.168.1.123"
    truncated = truncate_ip(full_ip)
    assert full_ip not in truncated


def test_sanitize_comment_strips_html():
    comment = sanitize_comment("<script>alert('xss')</script>Normal text")
    assert "<script>" not in comment
    assert "Normal text" in comment


def test_sanitize_comment_max_length():
    long_comment = "x" * 1000
    result = sanitize_comment(long_comment, max_chars=500)
    assert len(result) <= 500


def test_pseudonymize_prefix():
    result = pseudonymize_user_id("E0001", salt="test-salt")
    assert result.startswith("U-")
