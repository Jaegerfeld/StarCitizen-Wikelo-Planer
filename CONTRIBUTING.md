# Contributing / Conventions

These conventions mirror the [situation-report](https://github.com/Jaegerfeld/situation-report)
project, so quality standards stay consistent across projects. Scaled to this project's size
(a single stdlib generator + a self-contained HTML app).

## Quality gate

- **Lint:** [ruff](https://docs.astral.sh/ruff/) — rule sets `F, I, B, UP, C901`,
  line length 100, max cyclomatic complexity 15 (see [`pyproject.toml`](pyproject.toml)).
- **CI:** [`.github/workflows/quality.yml`](.github/workflows/quality.yml) runs `ruff check .`
  on every push/PR touching Python or config. ruff is **pinned** (`0.15.*`) so CI matches local.
- Run locally before pushing:

  ```bash
  pip install "ruff==0.15.*"
  python -m ruff check .          # or: ruff check --fix .
  ```

- For substantially larger Python surface, add **mypy** (typed core), **pytest + coverage**
  and a coverage badge as in situation-report. Not enabled here because the meaningful logic
  lives in the browser (`transform()` in the generated HTML), not in the thin Python generator.

## Commenting & docstrings

- Every module starts with a **docstring**: what it does, its data sources, and how to run it.
- Comments explain the **why** (rationale at decision points), not the obvious *what*.
  Example: why a value is pinned, why a rule is ignored, why a plausibility cap exists.
- Use section separators (`# ---- section ----`) to structure longer files.
- Keep comments and identifiers in the surrounding file's language and style.

## Versioning & changelog

- **[SemVer](https://semver.org/)** in [`version.py`](version.py) — the single source of truth
  (the app bakes it into its header). Bump: patch = fixes/wording, minor = features, major = breaking.
- Keep a **[CHANGELOG.md](CHANGELOG.md)** in the *Keep a Changelog* format; one entry per release.

## Branches & deploy

- Do non-trivial work on a **feature branch**; open a PR against `main`.
- `main` auto-builds and deploys to GitHub Pages, so **never push a broken intermediate state
  to `main`** — merge only once the build and checks are green.
- Verify data-shaping changes against a **golden reference** (diff the produced data against the
  previous known-good output) before merging.

## Docs & reach

- **Bilingual**: user-facing docs and UI in **English and German**
  ([`README.md`](README.md) EN, [`README.de.md`](README.de.md) DE).
- Prefer **self-contained, offline-capable** deliverables with **no external runtime deps**
  (standard library only) where feasible.
- **Cross-platform launchers** (`.bat` / `.sh` / `.command`).
- **Credit data sources** in the README.

## AI-assisted development

This project is developed largely with AI ([Claude Code](https://claude.com/claude-code)); state
that openly in the README.
