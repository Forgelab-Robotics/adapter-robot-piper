# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
```

## Pull requests

- Keep changes focused and explain the hardware or simulation behavior affected.
- Add tests for command validation, unit conversion, and lifecycle changes.
- Do not run CI or review tests against physical hardware.
- Document model provenance and license for every new asset.
- Do not commit credentials, private recordings, device identifiers, absolute
  machine paths, or personal information.
- Update `CHANGELOG.md` for user-visible behavior.

By submitting a contribution, you agree that it is licensed under Apache
License 2.0. Do not submit code or assets that you do not have the right to
redistribute. Third-party work must retain its original license and attribution.

## Hardware changes

Changes that can move a real robot must describe safe test conditions, speed,
joint range, emergency-stop readiness, and whether physical validation was
performed. Review `SAFETY.md` before any hardware test.
