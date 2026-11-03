## 1. Remove the header and key plumbing

- [x] 1.1 Drop the `idempotencyKey` parameter and `headers` option from `printBadge` in `src/data/repositories/checkin-repository.ts` and `src/infrastructure/checkin-repository.ts`
- [x] 1.2 Drop the `idempotencyKey` parameter from `PrintVisitorBadgeUseCase.execute` in `src/data/use-cases/print-visitor-badge.ts`
- [x] 1.3 In `use-badge-printing.ts`, remove `keysRef`, key generation and the 4xx key-reset logic; call `printVisitorBadgeUseCase.execute(row.id)`

## 2. Verify

- [x] 2.1 Update any tests that pass or assert an idempotency key for badge print
- [x] 2.2 Run `tsc`, lint and build
- [x] 2.3 Manually confirm on dev: print a badge, the preflight lists no `idempotency-key`, the PDF opens, and a repeat print shows the Reprint guidance
