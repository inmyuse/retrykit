# Contributing to retrykit

Thanks for your interest in improving retrykit! The library ships in two
languages that must stay behaviourally identical, so changes usually touch both
the `python/` and `typescript/` packages.

## Repository layout

```
python/       # the Python package + pytest suite
typescript/   # the TypeScript package + vitest suite
```

## Running the Python package

```bash
cd python
pip install -e ".[dev]"
pytest --cov=retrykit   # tests + coverage (target > 90%)
mypy                    # strict type checking
ruff check retrykit     # lint
```

## Running the TypeScript package

```bash
cd typescript
npm install
npm run typecheck       # tsc --noEmit, strict
npm run lint            # eslint, no `any`
npm test                # vitest
npm run build           # tsup -> dist (ESM + CJS + d.ts)
```

## Pull request guidelines

1. **Keep the two APIs in sync.** If you add or rename an option in one
   language, mirror it in the other (respecting each language's conventions —
   e.g. seconds in Python, milliseconds in TypeScript).
2. **Add tests.** New behaviour needs coverage in both suites; keep total
   coverage above 90%.
3. **Pass all gates locally** before opening a PR: tests, type checks
   (`mypy --strict`, `tsc --noEmit`) and linters (`ruff`, `eslint`).
4. **Update docs.** Touch the relevant `README.md` and add a `CHANGELOG.md`
   entry under an *Unreleased* heading.
5. **Keep commits focused** and write a clear description of the change and its
   motivation.

## Reporting bugs

Open an issue with a minimal reproduction, the language/version, and the
expected vs. actual behaviour. Thank you!
