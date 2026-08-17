# Open-source release audit

Audit date: 2026-08-17

## Decision

The audited snapshot is suitable for publication after it is exported into a
new Git repository with a clean initial history. Project-owned code and
documentation use Apache-2.0. Bundled robot assets retain their upstream MIT
licenses and attribution.

## Completed checks

- Public dependency installation:
  - `forge-common==1.0.1`
  - `forge-msgs==1.0.1`
  - `forge-robot==1.0.1`
- Editable package installation with the `test` extra succeeded.
- All 56 unit tests passed without physical hardware.
- CLI reported `agilex-piper 1.1.3`.
- MuJoCo loaded `assets/mjcf/piper_mujoco/scene.xml` with `nq=8`, `nu=7`.
- All YAML workflow and configuration files parsed successfully.
- `uv.lock` resolves Forge packages from `https://pypi.org/simple`.
- Wheel build succeeded and included `LICENSE`, `NOTICE`, and
  `THIRD_PARTY_NOTICES.md`.
- Secret scan reported zero findings in the publishable text tree.
- No file exceeds GitHub's 100 MiB hard limit. The largest file is under 8 MiB.
- Machine-specific paths, private repository URLs, and named validation
  operators were removed from the publishable snapshot.

## License findings

- Project-owned Python, configuration, workflows, and documentation:
  Apache-2.0.
- MuJoCo Menagerie Piper model and derived GLB/USD assets: MIT,
  `Copyright (c) 2024 RosenYin`.
- Piper URDF assets: MIT, `Copyright (c) 2024 RosenYin`.
- Runtime dependencies are installed from PyPI and are not vendored.
- `python-can` is LGPL-3.0-only. Source distribution is acceptable, but a
  bundled PyInstaller executable requires a separate binary-distribution
  license review.

See `THIRD_PARTY_NOTICES.md` for the detailed attribution map.

## Known limitations

- CI and the audit do not command physical hardware.
- The physical arm, gripper, firmware limits, CAN behavior, emergency stop,
  and lifecycle positions require site-specific validation.
- End-to-end Dora workflows require an external Forge runtime tree and built
  binaries configured through `FORGE_RUNTIME_ROOT` and `FORGE_RUNTIME_BIN`.
- MuJoCo reports non-fatal attach-policy warnings while loading the delivered
  scene; the model still loads with the expected actuator count.
- This audit is an engineering review, not legal advice or safety
  certification.

## Publication model

Only the audited current snapshot is published. The public repository starts
with one initial commit on `master`; prior development history is not part of
the public release.
