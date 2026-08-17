## Summary

- 

## Validation

- [ ] Public dependencies install with `pip install -e ".[test]"`.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] MuJoCo assets load, if assets or control semantics changed.
- [ ] No secrets, private recordings, machine paths, or personal data are included.
- [ ] Third-party asset provenance and licenses are documented.

## Hardware safety

- [ ] This change cannot command physical hardware.
- [ ] Or: physical testing followed `SAFETY.md`, used reduced speed and small motion, and had an operator at the emergency stop.

Describe any physical validation, affected joints, speed, limits, and observed behavior:

