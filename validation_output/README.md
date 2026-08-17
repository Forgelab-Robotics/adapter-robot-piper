# Local validation output

This directory is reserved for local, environment-specific acceptance output.
Generated files are ignored and must not be committed.

Suitable local artifacts include:

- redacted `list-devices --json` and role-check output;
- redacted `watch-state` JSONL captured during limited motion;
- MuJoCo sweep logs and screenshots;
- completed copies of the joint-sweep checklist;
- package, wheel, and PyInstaller smoke-test logs.

Before sharing an artifact, remove CAN identifiers, machine paths, usernames,
recordings, images containing people, credentials, and other site-specific
information. Do not treat local output as a portable hardware certification.
