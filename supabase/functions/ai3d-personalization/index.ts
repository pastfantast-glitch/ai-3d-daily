import { createRemoteJWKSet, jwtVerify } from 'npm:jose@6.1.0';
import { AUDIENCE, ISSUER, authorizeClaims, semanticSignals } from './policy.mjs';

const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`), { timeoutDuration: 5000 });
const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Vary': 'Authorization' };
function response(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers });
}

Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return response(405, { error: 'method_not_allowed' });
  const match = /^Bearer ([A-Za-z0-9_.-]+)$/.exec(req.headers.get('Authorization') || '');
  if (!match || match[1].length > 16000) return response(401, { error: 'unauthorized' });
  // Supabase's platform JWT check is disabled only because this handler verifies
  // GitHub's signature, issuer, audience, expiration and exact workflow itself.
  try {
    const { payload } = await jwtVerify(match[1], JWKS, {
      issuer: ISSUER, audience: AUDIENCE, algorithms: ['RS256'], maxTokenAge: '10m', clockTolerance: 5,
    });
    if (!authorizeClaims(payload)) return response(403, { error: 'workflow_not_allowed' });
  } catch {
    return response(401, { error: 'unauthorized' });
  }

  try {
    const base = Deno.env.get('SUPABASE_URL')!;
    const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const serviceHeaders = { apikey: key, Authorization: `Bearer ${key}` };
    const owners = await fetch(`${base}/rest/v1/app_owner?singleton=eq.true&select=user_id&limit=2`,
      { headers: serviceHeaders, signal: AbortSignal.timeout(8000) });
    if (!owners.ok) throw new Error('owner_lookup_failed');
    const owner = await owners.json();
    if (!Array.isArray(owner) || owner.length !== 1 || !owner[0]?.user_id) throw new Error('owner_unavailable');
    const result = await fetch(`${base}/rest/v1/user_sync_state?user_id=eq.${encodeURIComponent(owner[0].user_id)}&select=state&limit=2`,
      { headers: serviceHeaders, signal: AbortSignal.timeout(8000) });
    if (!result.ok) throw new Error('state_lookup_failed');
    const rows = await result.json();
    // A missing snapshot is unavailable, never silently reported as an empty profile.
    if (!Array.isArray(rows) || rows.length !== 1) throw new Error('state_unavailable');
    const signals = semanticSignals(rows[0].state);
    return response(200, { schema_version: 1, owner_verified: true, vote_count: signals.length, signals });
  } catch {
    return response(503, { error: 'preferences_unavailable' });
  }
});
