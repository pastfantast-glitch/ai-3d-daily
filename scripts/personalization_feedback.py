#!/usr/bin/env python3
"""Deterministic semantic personalization helpers.

This module mirrors the browser preference semantics without consuming bookmarks or
source/domain identity. It is safe for collection/ranking logic because raw user
feedback stays outside the repository; only bounded audit metadata may be committed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'personalization-feedback.json'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
HEX64_RE = re.compile(r'^[0-9a-f]{64}$')


def _number(value, default=0.0):
    if isinstance(value, bool):
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _parse_time(value):
    text = str(value or '').strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_config():
    cfg = json.loads(CONFIG.read_text('utf-8'))
    if int(cfg.get('version', 0) or 0) < 1:
        raise ValueError('personalization contract version must be >=1')
    effective = str(cfg.get('effective_date', '')).strip()
    if not DATE_RE.fullmatch(effective):
        raise ValueError('personalization effective_date must be YYYY-MM-DD')
    if cfg.get('mode') != 'supabase-semantic-feedback-v1':
        raise ValueError('personalization mode must be supabase-semantic-feedback-v1')

    source = cfg.get('source') or {}
    if source.get('provider') != 'supabase' or not str(source.get('project_ref', '')).strip():
        raise ValueError('personalization source must declare Supabase project_ref')
    if source.get('table') != 'user_sync_state' or source.get('state_path') != 'profile.votes':
        raise ValueError('personalization source must read user_sync_state profile.votes')
    if source.get('raw_profile_must_not_be_committed') is not True:
        raise ValueError('raw personalization profile must never be committed')
    if source.get('server_secret_in_repository') is not False:
        raise ValueError('server secret must never be stored in repository')

    signals = cfg.get('signals') or {}
    if _number(signals.get('like')) <= 0 or _number(signals.get('dislike')) >= 0:
        raise ValueError('like must be positive and dislike must be negative')
    if _number(signals.get('bookmark')) != 0 or signals.get('bookmark_affects_preference') is not False:
        raise ValueError('bookmark must remain zero-weight')

    dims = cfg.get('semantic_dimensions') or {}
    allowed = list(dims.get('allowed') or [])
    forbidden = set(dims.get('forbidden') or [])
    if allowed != ['category', 'tool', 'topic', 'tag']:
        raise ValueError('allowed semantic dimensions must be category/tool/topic/tag')
    if not {'domain', 'source', 'site', 'publisher'} <= forbidden:
        raise ValueError('source/domain dimensions must be forbidden')
    fit_weights = dims.get('fit_weights') or {}
    if set(fit_weights) != set(allowed):
        raise ValueError('fit_weights must cover exactly the allowed semantic dimensions')
    if abs(sum(_number(fit_weights.get(k)) for k in allowed) - 1.0) > 1e-9:
        raise ValueError('fit_weights must sum to 1.0')

    ranking = cfg.get('ranking') or {}
    max_mult = _number(ranking.get('max_rank_multiplier'), -1)
    if not (0 < max_mult <= 0.20):
        raise ValueError('max_rank_multiplier must be >0 and <=0.20')
    for key in ('admission_bypass', 'evidence_depth_bypass', 'registry_bypass', 'quality_gate_bypass', 'source_bonus', 'source_quota'):
        if ranking.get(key) is not False:
            raise ValueError(f'personalization ranking.{key} must be false')

    discovery = cfg.get('discovery') or {}
    if discovery.get('semantic_query_expansion') is not True or discovery.get('base_discovery_must_always_run') is not True:
        raise ValueError('semantic query expansion must supplement, never replace, base discovery')
    if not (0 <= _number(discovery.get('max_query_expansion_fraction'), -1) <= 0.20):
        raise ValueError('max_query_expansion_fraction must be <=0.20')
    if discovery.get('negative_feedback_may_hard_exclude') is not False or discovery.get('site_specific_expansion') is not False:
        raise ValueError('feedback cannot hard-exclude or create site-specific expansion')
    return cfg


def applies(date, cfg=None):
    cfg = cfg or load_config()
    value = str(date or '').strip()
    return bool(DATE_RE.fullmatch(value) and value >= str(cfg['effective_date']))


def age_factor(updated_at, as_of=None, cfg=None):
    cfg = cfg or load_config()
    updated = _parse_time(updated_at)
    if updated is None:
        return 1.0
    current = _parse_time(as_of) if as_of else datetime.now(timezone.utc)
    if current is None:
        current = datetime.now(timezone.utc)
    days = max(0.0, (current - updated).total_seconds() / 86400.0)
    decay = cfg.get('decay') or {}
    if days <= 7:
        return _number(decay.get('days_0_7'), 1.0)
    if days <= 30:
        return _number(decay.get('days_8_30'), 0.7)
    if days <= 90:
        return _number(decay.get('days_31_90'), 0.4)
    return _number(decay.get('days_91_plus'), 0.2)


def derive_weights(votes, as_of=None, cfg=None):
    cfg = cfg or load_config()
    votes = votes if isinstance(votes, dict) else {}
    caps = cfg.get('caps') or {}
    signals = cfg.get('signals') or {}
    out = {'category': {}, 'tool': {}, 'topic': {}, 'tag': {}}
    feature_keys = {'category': 'category', 'tool': 'tools', 'topic': 'topics', 'tag': 'tags'}

    for entry in votes.values():
        if not isinstance(entry, dict):
            continue
        vote = int(_number(entry.get('vote'), 0))
        if vote == 0:
            continue
        base = _number(signals.get('like') if vote > 0 else signals.get('dislike'))
        delta = base * age_factor(entry.get('updatedAt'), as_of=as_of, cfg=cfg)
        features = entry.get('features') or {}
        if not isinstance(features, dict):
            continue
        for group, feature_key in feature_keys.items():
            values = features.get(feature_key) or []
            if not isinstance(values, list):
                continue
            for raw in values:
                key = str(raw or '').strip()
                if key:
                    out[group][key] = out[group].get(key, 0.0) + delta

    for group, bucket in out.items():
        cap = abs(_number(caps.get(group), 0))
        if cap <= 0:
            bucket.clear()
            continue
        for key in list(bucket):
            bucket[key] = round(max(-cap, min(cap, bucket[key])), 2)
            if bucket[key] == 0:
                del bucket[key]
    return out


def profile_fingerprint(weights):
    normalized = json.dumps(weights or {}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def semantic_fit(weights, candidate_features, cfg=None):
    cfg = cfg or load_config()
    weights = weights if isinstance(weights, dict) else {}
    features = candidate_features if isinstance(candidate_features, dict) else {}
    caps = cfg.get('caps') or {}
    dim_weights = (cfg.get('semantic_dimensions') or {}).get('fit_weights') or {}
    aliases = {
        'category': ('category', 'categories'),
        'tool': ('tool', 'tools'),
        'topic': ('topic', 'topics'),
        'tag': ('tag', 'tags'),
    }
    total = 0.0
    for group, keys in aliases.items():
        values = []
        for key in keys:
            raw = features.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif raw:
                values.append(raw)
        names = {str(x or '').strip() for x in values if str(x or '').strip()}
        cap = abs(_number(caps.get(group), 0)) or 1.0
        matched = [_number((weights.get(group) or {}).get(name)) / cap for name in names if name in (weights.get(group) or {})]
        group_score = sum(matched) / len(matched) if matched else 0.0
        total += _number(dim_weights.get(group)) * max(-1.0, min(1.0, group_score))
    return round(max(-1.0, min(1.0, total)), 4)


def personalized_score(base_score, fit, cfg=None):
    cfg = cfg or load_config()
    base = max(0.0, min(100.0, _number(base_score)))
    fit = max(-1.0, min(1.0, _number(fit)))
    mult = _number((cfg.get('ranking') or {}).get('max_rank_multiplier'))
    return round(max(0.0, min(100.0, base * (1.0 + mult * fit))), 2)


def audit_errors(data, cfg=None):
    cfg = cfg or load_config()
    date = str((data or {}).get('date', '')).strip()
    if not applies(date, cfg):
        return []
    meta = ((data or {}).get('metadata') or {}).get('personalization')
    if not isinstance(meta, dict):
        return ['personalization metadata missing for effective date']

    errors = []
    audit_cfg = cfg.get('audit_metadata') or {}
    statuses = set(audit_cfg.get('allowed_statuses') or [])
    status = str(meta.get('status', '')).strip()
    if meta.get('contract') != cfg.get('mode'):
        errors.append('personalization.contract must match configured mode')
    if status not in statuses:
        errors.append(f'personalization.status must be one of {sorted(statuses)}')

    vote_count = meta.get('vote_count')
    if isinstance(vote_count, bool) or not isinstance(vote_count, int) or vote_count < 0:
        errors.append('personalization.vote_count must be integer >=0')
        vote_count = -1
    fingerprint = str(meta.get('profile_fingerprint') or '').strip()
    if status in {'applied', 'empty'} and not HEX64_RE.fullmatch(fingerprint):
        errors.append('personalization.profile_fingerprint must be sha256 when Supabase profile is available')
    if status == 'applied' and vote_count <= 0:
        errors.append('personalization applied requires vote_count >0')
    if status == 'empty' and vote_count != 0:
        errors.append('personalization empty requires vote_count=0')
    if status == 'unavailable':
        if fingerprint:
            errors.append('personalization unavailable must not claim profile_fingerprint')
        if not str(meta.get('reason', '')).strip():
            errors.append('personalization unavailable requires reason')

    expected_mult = _number((cfg.get('ranking') or {}).get('max_rank_multiplier'))
    if abs(_number(meta.get('max_rank_multiplier'), -1) - expected_mult) > 1e-9:
        errors.append('personalization.max_rank_multiplier must match contract')
    expected_q = _number((cfg.get('discovery') or {}).get('max_query_expansion_fraction'))
    if abs(_number(meta.get('max_query_expansion_fraction'), -1) - expected_q) > 1e-9:
        errors.append('personalization.max_query_expansion_fraction must match contract')
    for key in ('raw_profile_committed', 'bookmarks_used', 'domain_weights_used', 'admission_bypass', 'quality_gate_bypass', 'source_quota'):
        if meta.get(key) is not False:
            errors.append(f'personalization.{key} must be false')
    return errors
