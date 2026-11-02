## 1. Write the rule

- [x] 1.1 Add §5 "Test scope while implementing a change" to `.claude/rules/testing-standards.md`. Cover: what the targeted test set is (the changed feature's tests, tests of dependent areas, the API documentation tests for route or schema changes); how to find dependent areas (design.md Decision 2); one sequential pytest run, never parallel; what to do when a task says "full suite" (run the targeted set and note it); the full suite is kept for the CI gate and for runs the user asks for; the report lists the modules run and the dependent areas included, with reasons
- [x] 1.2 In the Testing section of `.claude/rules/project-rules.md`, replace "All tests must pass before proposing significant changes" with a short statement of the rule that points to `testing-standards.md` §5 and says the full suite is the CI gate's job

## 2. Wire it into the OpenSpec apply workflow

- [x] 2.1 Add `operations.apply.guidance` entries to `openspec/config.yaml` that state the rule in brief and point to `testing-standards.md` §5. Leave the commented examples in place
- [x] 2.2 Check that the guidance appears in `openspec instructions apply --change scope-tests-to-change-requests --json` (or its equivalent output) and that `openspec validate scope-tests-to-change-requests --strict` passes

## 3. Check consistency

- [x] 3.1 Confirm that `git-workflow.md` §3 and §4 (PR checklist, CI gate) still say "full `pytest`" for merge, and that nothing in the new text contradicts them
- [x] 3.2 Skip pytest for this change: it edits only rule and config files, so no test module covers it. Note this in the completion summary — done: no pytest run, only rule/config files changed
