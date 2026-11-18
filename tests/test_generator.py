"""Tests for synthetic data generator."""
from __future__ import annotations
import pytest
from src.ueba.generator.org import generate_org, CITY_COORDS
from src.ueba.config import get_config


def test_org_user_count():
    org = generate_org(seed=42, num_users=60)
    assert len(org.users) == 60


def test_org_resource_count():
    org = generate_org(seed=42, num_resources=150)
    assert len(org.resources) == 150


def test_org_contractor_count():
    org = generate_org(seed=42, num_users=60, num_contractors=10)
    contractors = [u for u in org.users if u.is_contractor]
    assert len(contractors) == 10


def test_org_night_shift_count():
    org = generate_org(seed=42)
    night_shift = [u for u in org.users if u.is_night_shift]
    assert len(night_shift) == 3


def test_org_part_time_count():
    org = generate_org(seed=42)
    part_time = [u for u in org.users if u.is_part_time]
    assert len(part_time) == 2


def test_org_deterministic():
    org1 = generate_org(seed=42)
    org2 = generate_org(seed=42)
    assert [u.user_id for u in org1.users] == [u.user_id for u in org2.users]


def test_resource_sensitivity_distribution():
    org = generate_org(seed=42, num_resources=150)
    sensitivities = {r.sensitivity for r in org.resources}
    assert "Restricted" in sensitivities
    assert "Confidential" in sensitivities
    assert "Public" in sensitivities


def test_no_real_names_in_user_ids():
    org = generate_org(seed=42)
    for user in org.users:
        assert user.user_id.startswith("E")
        assert user.user_id[1:].isdigit()


def test_city_coords_has_expected_cities():
    assert "New York" in CITY_COORDS
    assert "Tokyo" in CITY_COORDS
    assert "London" in CITY_COORDS
