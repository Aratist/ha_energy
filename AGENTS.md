# AGENTS.md

This repository contains a Home Assistant custom integration (Python) in `custom_components/energy_manager`. See [README.md](README.md) for behavior.

- Decision logic lives in `engine.py` and must stay free of `homeassistant` imports so it can be unit-tested.
- Validate with `python -m pytest tests` (engine tests, no Home Assistant install needed).

## Working conventions

- Prefer small, targeted changes over broad refactors.
- Confirm the project language, framework, and build/test entry points before making architectural changes.
- When the repo is empty or ambiguous, ask for the intended stack or target files instead of inferring one.
- Keep changes easy to review and aligned with the existing structure of the repository.
- Do not add heavy dependencies or tooling unless the project clearly requires them.

## Before editing code

- Check whether the repository already contains a framework, package manifest, or build configuration.
- If a project exists, use its native commands for validation instead of inventing new ones.
- Prefer the smallest relevant validation command (for example, a focused test or build target) over a broad suite.

## Documentation and discovery

- Link to existing documentation rather than duplicating it.
- If docs are missing, add only concise, actionable guidance that helps future agents understand how to operate in this repo.

## Default behavior for this repo

- Assume the repo may evolve from a blank state; do not hardcode a framework, package manager, or deployment setup without evidence.
- Keep instructions short and framework-agnostic until a project structure is present.

## Expected workflow for future tasks

1. Inspect the repository for manifests, source folders, and build/test scripts.
2. Identify the actual stack and conventions used in the codebase.
3. Make the smallest valid change for the requested task.
4. Validate with the most relevant command and report the outcome clearly.
