import test from 'node:test';
import assert from 'node:assert/strict';
import { authorizeClaims, semanticSignals } from './policy.mjs';

const claims = {
  repository: 'pastfantast-glitch/ai-3d-daily', repository_id: '1341366102', repository_owner_id: '316682659',
  ref: 'refs/heads/main', ref_type: 'branch', event_name: 'schedule', runner_environment: 'github-hosted',
  run_id: '123', workflow_ref: 'pastfantast-glitch/ai-3d-daily/.github/workflows/daily-collector.yml@refs/heads/main',
  iat: 1000, exp: 1600,
};
test('trust only the exact repository and main Collector or smoke workflow', () => {
  assert.equal(authorizeClaims(claims, 1100), true);
  assert.equal(authorizeClaims({...claims, workflow_ref: claims.workflow_ref.replace('daily-collector', 'personalization-check')}, 1100), true);
  for (const change of [
    {repository_id: '999'}, {repository_owner_id: '999'}, {repository: 'attacker/fork'},
    {ref: 'refs/heads/feature'}, {event_name: 'pull_request'}, {event_name: 'pull_request_target'},
    {workflow_ref: claims.workflow_ref.replace('daily-collector', 'untrusted')},
    {workflow_ref: claims.workflow_ref.replace('@refs/heads/main', '@refs/heads/feature')},
    {exp: 1099}, {iat: 0}, {iat: 1300}, {iat: undefined}, {exp: undefined},
  ]) assert.equal(authorizeClaims({...claims, ...change}, 1100), false);
});
test('strip identities, source dimensions, bookmarks and cached weights', () => {
  const signals = semanticSignals({profile: {weights: {tool: {Houdini:999}}, votes: {
    'private-article-id': {vote:1, title:'Private title', source:'https://private.invalid', updatedAt:'2026-10-01T00:00:00Z', features:{category:['engine-art'],tools:['Houdini'],topics:['Shader'],tags:['https://publisher.invalid'],domain:['publisher.invalid']}},
    'no-vote': {vote:0}, 'bad-vote': {vote:true},
  }}, bookmarks: {items: {'private-bookmark': {title:'secret'}}}});
  assert.equal(signals.length, 1);
  assert.deepEqual(Object.keys(signals[0]).sort(), ['features','updatedAt','vote']);
  assert.deepEqual(Object.keys(signals[0].features).sort(), ['category','tags','tools','topics']);
  const text = JSON.stringify(signals);
  for (const forbidden of ['private-', 'Private title', 'publisher.invalid', 'weights', 'bookmarks', 'domain']) assert.equal(text.includes(forbidden), false);
  assert.deepEqual(semanticSignals({}), []);
});
