# Execution Intent Two-Phase Commit (PR-0.2)

This adds a deterministic prepare/commit workflow around IG order submission so the engine avoids duplicate same-ticket submissions during brief retries or partial visibility windows.

## Module
- `app/execution_two_phase_commit.py`

## Behavior
1. **Prepare phase**: before `open_position`, the engine records a PREPARED intent keyed by `(epic, direction, size)`.
2. **Commit phase**: after accepted/confirmed order outcomes, the intent is finalized as COMMITTED with deal references.
3. **Abort phase**: if submit fails or confirm/book reconciliation fails, the intent is finalized as ABORTED.
4. **Duplicate prevention**: new prepares for the same key are rejected while an active PREPARED intent is still within hold window.

## Integration
- `app/ig_execution_engine.py`

## Operational impact
- Reduces accidental small-ticket churn from repeat submissions during uncertain broker-response windows.
- Keeps execution plumbing fail-closed for duplicate rapid retries while allowing normal re-entry after abort/commit.
