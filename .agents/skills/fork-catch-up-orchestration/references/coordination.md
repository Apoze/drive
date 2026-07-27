# Coordination

Use this reference when catch-up work needs another agent, reviewer, QA pass, or
parallel worker. Keep the protocol generic and prefer any coordination mechanism
provided by the current environment.

## Delegate Only When Useful

Delegate when the task is:

- bounded and independently verifiable;
- separable from the sender's immediate next step;
- safe to run without private context that cannot be shared;
- clear about files, commits, branch, environment, and expected output.

Do not delegate an urgent blocker if the sender cannot make progress until the
answer returns. Handle that work locally.

## Handoff Contents

Every handoff should include:

- repository path and branch;
- source remote, target remote, and relevant commit range;
- approved mode: audit, execution, or publication;
- exact lot or scenario;
- files or areas owned by the receiver;
- validation expected;
- stop conditions;
- required report destination.

Do not include secrets, cookies, tokens, private keys, or full signed URLs.

## Wait Rule

After delegating, stop active polling unless the environment provides an
explicit wait primitive and the result is needed for the next step. Continue
non-overlapping work or report that the handoff is pending.

## Completion Routing

The receiver's report should include status, files changed, validation,
remaining work, and blockers. Route concrete QA or review failures back to the
agent that can fix them. Escalate to the user only for authorization,
publication, destructive history changes, security/product decisions, or
ambiguous tradeoffs.

## Parallel Safety

When multiple agents work in parallel, give each a disjoint write scope and
remind them not to revert unrelated edits. If scopes overlap, serialize the
work or introduce an integration step before validation.
