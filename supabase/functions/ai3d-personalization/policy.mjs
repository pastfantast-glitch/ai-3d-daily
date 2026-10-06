// Only these main-branch workflows may read the owner's semantic feedback.
export const ISSUER = 'https://token.actions.githubusercontent.com';
export const AUDIENCE = 'https://epumcdxfkcujulqrcjrw.supabase.co/functions/v1/ai3d-personalization';
const REPO = 'pastfantast-glitch/ai-3d-daily';
const WORKFLOWS = new Set([
  `${REPO}/.github/workflows/daily-collector.yml@refs/heads/main`,
  `${REPO}/.github/workflows/personalization-check.yml@refs/heads/main`,
]);

export function authorizeClaims(claims, now = Date.now() / 1000) {
  return claims.repository === REPO && claims.repository_id === '1341366102'
    && claims.repository_owner_id === '316682659'
    && claims.ref === 'refs/heads/main' && claims.ref_type === 'branch'
    && WORKFLOWS.has(claims.workflow_ref)
    && ['push', 'schedule', 'workflow_dispatch'].includes(claims.event_name)
    && claims.runner_environment === 'github-hosted'
    && /^\d+$/.test(String(claims.run_id || ''))
    && Number.isFinite(claims.iat) && claims.iat <= now + 5 && now - claims.iat <= 600
    && Number.isFinite(claims.exp) && claims.exp > now;
}

// Never return account IDs, article IDs/titles/URLs, bookmarks or stored weights.
export function semanticSignals(state) {
  const votes = state?.profile?.votes;
  if (!votes || typeof votes !== 'object' || Array.isArray(votes)) return [];
  const signals = [];
  for (const entry of Object.values(votes)) {
    if (!entry || ![1, -1].includes(entry.vote)) continue;
    const features = Object.create(null);
    for (const key of ['category', 'tools', 'topics', 'tags']) {
      const values = entry.features?.[key];
      features[key] = Array.isArray(values) ? [...new Set(values.filter(v =>
        typeof v === 'string' && v.trim() && v.length <= 80 && !/[\r\n]|https?:|www\./i.test(v)
      ).map(v => v.trim()))].slice(0, 32) : [];
    }
    signals.push({ vote: entry.vote, updatedAt: typeof entry.updatedAt === 'string' ? entry.updatedAt.slice(0, 64) : null, features });
  }
  if (signals.length > 10000) throw new Error('profile_too_large');
  return signals;
}
