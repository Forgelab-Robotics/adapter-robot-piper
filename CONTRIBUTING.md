# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Development setup

```bash
uv sync --frozen --extra test
uv run python -m unittest discover -s tests -v
uv build
```

When dependencies change, update `uv.lock`, rerun the frozen checks, and audit
the exported locked requirements as described in `RELEASING.md`.

## Pull requests

- Keep changes focused and explain the hardware or simulation behavior affected.
- Add tests for command validation, unit conversion, and lifecycle changes.
- Do not run CI or review tests against physical hardware.
- Document model provenance and license for every new asset.
- Do not commit credentials, private recordings, device identifiers, absolute
  machine paths, or personal information.
- Update `CHANGELOG.md` for user-visible behavior.
- Complete `.github/pull_request_template.md` and ensure the `test`, `secrets`,
  and dependency-audit checks pass.

By submitting a contribution, you agree that it is licensed under Apache
License 2.0. Do not submit code or assets that you do not have the right to
redistribute. Third-party work must retain its original license and attribution.

## Hardware changes

Changes that can move a real robot must describe safe test conditions, speed,
joint range, emergency-stop readiness, and whether physical validation was
performed. Review `SAFETY.md` before any hardware test.
