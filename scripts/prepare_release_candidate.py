#!/usr/bin/env python3
"""Hybrid-aware pre-ready entry point.

Keeps the canonical prepare sequence intact while inserting the repository-owned
hybrid discovery contract, audited low-volume registry gate, and audited release
input exception. The core remains the only code that creates .ready.
"""
import prepare_release_candidate_core as core

ORIGINAL_RUN = core.run


def hybrid_run(script: str, *args: str) -> None:
    if script == 'check_collection_contract.py':
        ORIGINAL_RUN(script, *args)
        ORIGINAL_RUN('check_discovery_hybrid_contract.py')
        return
    if script == 'normalize_registry_identity.py':
        return ORIGINAL_RUN('normalize_registry_identity_hybrid.py', *args)
    if script == 'check_release_input.py':
        return ORIGINAL_RUN('check_release_input_hybrid.py', *args)
    return ORIGINAL_RUN(script, *args)


core.run = hybrid_run
core.main()
