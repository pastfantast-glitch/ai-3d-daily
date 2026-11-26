import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceInventory} from './admin-source-state.mjs';
test('current inventory does not use old zero-valued Collector snapshots',()=>{
 const ops={reserve_complete:true,checked_at:'2026-11-26T10:00:00Z',reserve:[{source_id:'godot',state:'recheck_required'},{source_id:'godot',state:'source_unavailable'},{source_id:'other',state:'recheck_required'}],source_supply:[{source_id:'godot',reserve:1}]};
 assert.deepEqual(sourceInventory(ops,'godot'),{total:2,pending:1,unavailable:1,checkedAt:ops.checked_at});
 assert.equal(sourceInventory({...ops,reserve_complete:false},'godot'),null);
 assert.equal(sourceInventory({...ops,source_supply:[{source_id:'godot',reserve:null}]},'godot'),null);
 assert.equal(sourceInventory(ops,'new-draft-source'),null);
 assert.equal(sourceInventory(null,'godot'),null);
 assert.deepEqual(sourceInventory({...ops,reserve:[],source_supply:[{source_id:'godot',reserve:0}]},'godot'),{total:0,pending:0,unavailable:0,checkedAt:ops.checked_at});
});
