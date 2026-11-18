"""Tests for context dampening."""
from __future__ import annotations
import pytest
from src.ueba.context_dampening import apply_context_dampening


def test_dampening_reduces_score():
    indicators = [{
        "indicator_id": "test-1",
        "name": "NEW_COUNTRY",
        "severity_points": 35.0,
        "confidence": 0.9,
        "description": "New country login",
        "evidence_event_ids": [],
        "observed_value": "DE",
        "baseline_value": "US",
        "why_it_matters": "Test",
    }]
    contexts = [{
        "context_id": "ctx-001",
        "context_type": "approved_travel",
        "start_time": "2024-02-01T00:00:00",
        "end_time": "2024-02-07T23:59:59",
        "approved_by_role": "Manager",
        "notes": "Business travel to Berlin",
    }]
    dampened, applied = apply_context_dampening(indicators, contexts)
    assert len(dampened) == 1
    assert dampened[0]["severity_points"] < 35.0
    assert len(applied) == 1
    assert applied[0]["context_type"] == "approved_travel"


def test_undampenable_indicators_not_dampened():
    indicators = [{
        "indicator_id": "test-2",
        "name": "IMPOSSIBLE_TRAVEL",
        "severity_points": 60.0,
        "confidence": 1.0,
        "description": "Impossible travel",
        "evidence_event_ids": [],
        "observed_value": 1200,
        "baseline_value": 0,
        "why_it_matters": "Test",
    }]
    contexts = [{
        "context_id": "ctx-002",
        "context_type": "approved_travel",
        "start_time": "2024-02-01T00:00:00",
        "end_time": "2024-02-07T23:59:59",
        "approved_by_role": "Manager",
        "notes": "Travel",
    }]
    dampened, applied = apply_context_dampening(indicators, contexts)
    assert dampened[0]["severity_points"] == 60.0
    assert len(applied) == 0


def test_no_context_no_dampening():
    indicators = [{
        "indicator_id": "test-3",
        "name": "UNUSUAL_HOUR",
        "severity_points": 20.0,
        "confidence": 0.8,
        "description": "Unusual hour",
        "evidence_event_ids": [],
        "observed_value": 3,
        "baseline_value": 10,
        "why_it_matters": "Test",
    }]
    dampened, applied = apply_context_dampening(indicators, [])
    assert dampened[0]["severity_points"] == 20.0
    assert len(applied) == 0


def test_dampening_does_not_eliminate_indicator():
    indicators = [{
        "indicator_id": "test-4",
        "name": "DOWNLOAD_VOLUME_SPIKE",
        "severity_points": 40.0,
        "confidence": 0.9,
        "description": "Big download",
        "evidence_event_ids": [],
        "observed_value": 5000000,
        "baseline_value": 100000,
        "why_it_matters": "Test",
    }]
    contexts = [{
        "context_id": "ctx-003",
        "context_type": "month_end_close",
        "start_time": "2024-01-29T00:00:00",
        "end_time": "2024-01-31T23:59:59",
        "approved_by_role": "Finance Manager",
        "notes": "Month end",
    }]
    dampened, applied = apply_context_dampening(indicators, contexts)
    assert len(dampened) == 1
    assert dampened[0]["severity_points"] > 0
