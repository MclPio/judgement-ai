# Pipeline

## Milestone Template

For each milestone, write down:

- a plan
- code files to change
- testing needs

If a milestone changes public behavior, update docs in the same pass after it is complete.

## Active Milestones

### M9. Preview Command

Plan:

- add a dedicated `judgement-ai preview` command so users can inspect the resolved prompt and request shape before grading
- keep v1 intentionally simple and always available by using built-in placeholder data instead of loading real query/result files
- help users verify prompt mode, provider resolution, response mode, and advanced config effects without spending provider time or debugging a live run

Behavior agreed for v1:

- command name is `judgement-ai preview`
- use placeholder input by default, not the first real query/result
- placeholder query should be a simple example string
- placeholder result should include `title` and `description`, not URL
- preview should work even if `queries` and `search.results_file` are not configured
- print:
  - prompt mode
  - resolved provider
  - response mode
  - rendered prompt
  - request payload shape
- redact any sensitive values if they appear in preview output
- do not make any provider network calls

Code focus:

- `judgement_ai/cli/main.py`
- `judgement_ai/cli/common.py`
- `judgement_ai/cli/commands/preview.py`
- `judgement_ai/prompts.py`
- `judgement_ai/grading/providers.py`
- `README.md`
- `docs/configuration.md`

Implementation notes:

- reuse the same config-loading and override resolution path as `grade` where practical
- build the prompt exactly the same way the grader would, but with placeholder query/result fields
- expose the resolved payload as a preview artifact without sending it
- keep this read-only and side-effect free
- do not add a real-data preview mode in v1

Test minimum:

- `source .venv/bin/activate`
- `python3 -m pytest tests/test_cli.py tests/test_prompts.py tests/test_grader.py`
- `python3 -m ruff check .`

### M10. Final Documentation Update and Test Coverage Check

Plan:

- go over the CLI and Library files
- be sure `examples` and `docs` are up to date, simple and helpful
- make sure coverage includes important things like retries, failure logs, etc...

## Default Execution Order

Work on only one milestone at a time unless the user says otherwise.

## Exit Criteria

A milestone is complete when:

- the plan was implemented
- tests pass
- broader checks were run when the change crosses module boundaries
- docs match the shipped behavior
- the next milestone can start without re-reading stale notes
