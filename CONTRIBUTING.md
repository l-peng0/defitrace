# Contributing

This project is still early, so the goal is simple:

- keep changes small
- keep outputs easy to trace
- keep comments clear and kind

## Branches

Use short branch names that explain the job.

Examples:

- `feature/augmentation-source-fetch`
- `fix/run-state-write-order`
- `docs/mvp-readme`

## Commits

Try to make each commit do one thing.

Good examples:

- `Add augmentation MVP pipeline and CLI`
- `Ignore generated runs and output folders`
- `Document PR and review expectations`

## Pull requests

Each PR should explain:

- what changed
- why it changed
- how you checked it
- what is still missing or risky

If the change affects JSON outputs, include one short example of the new output shape.

## Code style

Please keep code plain and easy to scan.

- prefer small functions
- prefer clear names over clever names
- keep side effects obvious
- write JSON outputs with stable field names
- avoid mixing unrelated refactors into feature work

## GitHub review comments

When leaving review comments, aim for comments that help the next person act fast.

Good review comments usually do three things:

1. point to the exact problem
2. explain the real impact
3. suggest the next move

Try to use this shape:

```text
Problem: This run file is written before the stage is marked complete.
Impact: The saved state can look stale even when the script succeeds.
Suggestion: Update the in-memory run state first, then write the file once.
```

Keep comments about the code, not the person.

Prefer calm wording like:

- `This can break when...`
- `I think this output will be hard to reuse because...`
- `Could we move this so the JSON stays consistent?`

Avoid vague comments like:

- `bad`
- `wrong`
- `fix this`

## Public deployment safety

Before any future public deployment:

- do not commit secrets or tokens
- keep generated data and scratch outputs out of the repo
- document any environment variables in the README or a future `.env.example`
- treat external data sources as unstable and validate missing fields carefully
