"""Read private semantic feedback in memory and apply bounded Collector signals."""
from __future__ import annotations

import math
import os
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from personalization_feedback import derive_weights, personalized_score, profile_fingerprint, semantic_fit

TOOLS = ('Meshy', 'Tripo', 'Hunyuan3D', 'Hunyuan', 'Blender', 'Maya', '3ds Max', 'ZBrush',
         'Substance', 'Unreal Engine', 'Unreal', 'UE5', 'Unity', 'Cascadeur', 'Houdini',
         'Arnold', 'ComfyUI', 'Rokoko', 'MetaHuman', 'MotionBuilder', 'Move AI', 'DeepMotion',
         'AccuRIG', 'Godot', 'Bifrost', 'Cycles')
TOPICS = (
    ('Retopology', r'retopo|retopology|拓樸|重拓'), ('UV', r'\buv\b|unwrap|拆\s*uv|uv拆'),
    ('Texture', r'texture|textur|貼圖'), ('PBR', r'\bpbr\b|roughness|metallic|normal bake'),
    ('Multi-view', r'multi[- ]?view|multiview|多視圖|四視圖'),
    ('Image-to-3D', r'image[- ]?to[- ]?3d|image to 3d|圖像.?3d|圖片.?3d'),
    ('Text-to-3D', r'text[- ]?to[- ]?3d|text to 3d|文字.?3d'),
    ('Rigging', r'rigging|\brig\b|綁定|骨架'), ('Animation', r'animation|動畫|動作'),
    ('Mocap', r'mocap|motion capture|動捕'), ('Retarget', r'retarget|重定向'),
    ('Facial', r'facial|face rig|臉部|表情'), ('Shader', r'shader|材質球|著色'),
    ('NPR / Toon', r'\bnpr\b|toon|stylized rendering|卡通渲染|賽璐璐'),
    ('Rendering', r'render|渲染|cycles|arnold'), ('Lighting', r'lighting|light|燈光|光照|lumen'),
    ('Character', r'character|角色|human|人物'),
    ('Environment', r'environment|world|場景|terrain|landscape|open world'),
    ('Prop / Hard Surface', r'prop|hard.?surface|weapon|vehicle|mechanical|道具|硬表面|武器|載具|機械'),
    ('Procedural', r'procedural|geometry nodes|node.?based|程序化|幾何節點'),
    ('Optimization', r'optimization|performance|lod|hlod|draw.?call|效能|優化'),
    ('Automation / Pipeline', r'pipeline|automation|batch|api|workflow|流程|自動化'),
)
CATEGORIES = {'ai-generation', '3d-production', '3d-animation', 'engine-art', 'emerging-case', 'blender-dcc'}


def neutral_audit(cfg, reason):
    return {
        'contract': cfg['mode'], 'status': 'unavailable', 'vote_count': 0, 'reason': reason,
        'max_rank_multiplier': float(cfg['ranking']['max_rank_multiplier']),
        'max_query_expansion_fraction': float(cfg['discovery']['max_query_expansion_fraction']),
        'raw_profile_committed': False, 'bookmarks_used': False, 'domain_weights_used': False,
        'admission_bypass': False, 'quality_gate_bypass': False, 'source_quota': False,
        'ranking_adjusted_count': 0, 'semantic_expansion_candidates': 0,
    }


def _validated_signals(body):
    if not isinstance(body, dict) or set(body) != {'schema_version', 'owner_verified', 'vote_count', 'signals'}:
        raise ValueError('invalid bridge response')
    signals = body['signals']
    if body['schema_version'] != 1 or body['owner_verified'] is not True or not isinstance(signals, list):
        raise ValueError('owner not verified')
    if isinstance(body['vote_count'], bool) or body['vote_count'] != len(signals) or len(signals) > 10000:
        raise ValueError('invalid signal count')
    out = {}
    for index, entry in enumerate(signals):
        if not isinstance(entry, dict) or set(entry) != {'vote', 'updatedAt', 'features'}:
            raise ValueError('invalid signal')
        if isinstance(entry['vote'], bool) or entry['vote'] not in (-1, 1):
            raise ValueError('invalid vote')
        features = entry['features']
        if not isinstance(features, dict) or set(features) != {'category', 'tools', 'topics', 'tags'}:
            raise ValueError('invalid semantic dimensions')
        for group, values in features.items():
            if not isinstance(values, list) or len(values) > 32:
                raise ValueError('invalid feature list')
            if any(not isinstance(v, str) or not v.strip() or len(v) > 80 or re.search(r'[\r\n]|https?:|www\.', v, re.I) for v in values):
                raise ValueError('invalid feature')
        if not isinstance(entry['updatedAt'], (str, type(None))) or len(entry['updatedAt'] or '') > 64:
            raise ValueError('invalid timestamp')
        # Only recognized semantic vocabularies participate in ranking/discovery.
        out[str(index)] = {
            **entry, 'features': {
                'category': [v for v in features['category'] if v in CATEGORIES],
                'tools': [v for v in features['tools'] if v in TOOLS],
                'topics': [v for v in features['topics'] if v in {name for name, _ in TOPICS}],
                'tags': [v for v in features['tags'] if v in set(TOOLS) | {name for name, _ in TOPICS}],
            },
        }
    return out


def load_owner_preferences(cfg, *, as_of=None, env=None, session=None):
    """No credentials, raw feedback or semantic weights are persisted or logged."""
    env = os.environ if env is None else env
    http = requests.Session() if session is None else session
    weights = {'category': {}, 'tool': {}, 'topic': {}, 'tag': {}}
    audit = neutral_audit(cfg, 'Authenticated owner preference bridge is unavailable; neutral ranking used.')
    try:
        reader = cfg['source']['collector_reader']
        endpoint = f"https://{cfg['source']['project_ref']}.supabase.co/functions/v1/{reader['function']}"
        if reader['authentication'] != 'github-actions-oidc' or reader['function'] != 'ai3d-personalization':
            raise ValueError('invalid reader')
        timeout = int(reader['timeout_seconds'])
        if not 5 <= timeout <= 30:
            raise ValueError('unbounded timeout')
        token_url = env.get('ACTIONS_ID_TOKEN_REQUEST_URL', '')
        token_key = env.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN', '')
        parsed = urlparse(token_url)
        if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.actions.githubusercontent.com') or not token_key:
            raise ValueError('OIDC runtime missing')
        query = [(k, v) for k, v in parse_qsl(parsed.query) if k != 'audience'] + [('audience', endpoint)]
        token_url = urlunparse(parsed._replace(query=urlencode(query)))
        token_response = http.get(token_url, headers={'Authorization': f'Bearer {token_key}'}, timeout=timeout, allow_redirects=False)
        token_response.raise_for_status()
        if token_response.status_code != 200:
            raise ValueError('OIDC redirect rejected')
        token = token_response.json().get('value')
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{20,16000}', token):
            raise ValueError('invalid OIDC token')
        # Mask before any subsequent request; exceptions are never interpolated.
        if env.get('GITHUB_ACTIONS') == 'true':
            print(f'::add-mask::{token}')
        response = http.post(endpoint, headers={'Authorization': f'Bearer {token}'}, timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('bridge redirect rejected')
        if len(response.content) > 4000000:
            raise ValueError('bridge response too large')
        votes = _validated_signals(response.json())
        weights = derive_weights(votes, as_of=as_of, cfg=cfg)
        audit.update(status='applied' if votes else 'empty', vote_count=len(votes),
                     profile_fingerprint=profile_fingerprint(weights), reader='github-actions-oidc-owner-v1')
        audit.pop('reason', None)
    except (KeyError, TypeError, ValueError, requests.RequestException):
        pass
    return weights, audit


def candidate_features(candidate):
    text = ' '.join(str(candidate.get(k) or '') for k in ('title', 'description', 'summary', 'subcategory'))
    return {
        'category': [candidate['category']] if candidate.get('category') in CATEGORIES else [],
        'tool': [name for name in TOOLS if re.search(re.escape(name), text, re.I)],
        'topic': [name for name, pattern in TOPICS if re.search(pattern, text, re.I)],
        'tag': [name for name in TOOLS if re.search(re.escape(name), text, re.I)] + [name for name, pattern in TOPICS if re.search(pattern, text, re.I)],
    }


def apply_candidate_personalization(candidates, weights, cfg):
    adjusted = 0
    for candidate in candidates:
        base = candidate.setdefault('base_ranking_score', candidate['ranking_score'])
        fit = semantic_fit(weights, candidate_features(candidate), cfg=cfg)
        score = personalized_score(base, fit, cfg=cfg)
        candidate['ranking_score'] = score
        adjusted += int(score != base)
    return adjusted


def positive_expansion_terms(weights, cfg):
    terms = []
    for group, allowed in (('tool', set(TOOLS)), ('topic', {name for name, _ in TOPICS})):
        for name, weight in (weights.get(group) or {}).items():
            if name in allowed and weight > 0:
                terms.append((weight / float(cfg['caps'][group]), name))
    return list(dict.fromkeys(name for _, name in sorted(terms, key=lambda x: (-x[0], x[1]))))[:int(cfg['discovery']['max_positive_expansion_terms'])]


def expand_source_links(links, base_limit, terms, cfg):
    """Keep all base discovery; add <=20% semantic matches from the same source."""
    base = list(links[:base_limit])
    budget = math.floor(len(base) * float(cfg['discovery']['max_query_expansion_fraction']))
    if not terms or not budget:
        return base, set()
    extra = [pair for pair in links[base_limit:] if any(term.casefold() in pair[1].casefold() for term in terms)][:budget]
    return base + extra, {url for url, _ in extra}
