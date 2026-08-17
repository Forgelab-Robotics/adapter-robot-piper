# Changelog

All notable changes to this project are documented here.

The project follows Semantic Versioning. Dates use the `YYYY-MM-DD` format.

## Unreleased

### Added

- Locked-delivery and example-configuration contract tests.
- Release checklist, local validation-output policy, and dependency audit CI.

### Changed

- Standardized development, CI, and release commands on frozen `uv.lock`
  environments.
- Expanded configuration, validation, and troubleshooting documentation.

### Removed

- Removed the standalone security-policy and code-of-conduct files to align the
  public adapter documentation set. Security reports continue through GitHub
  private vulnerability reporting.

## [1.1.3] - 2026-08-17

### Added

- Public PyPI installation for Forge dependencies.
- Apache-2.0 licensing for project-owned code and documentation.
- Third-party notices for MIT-licensed robot assets.
- Hardware safety, security, and contribution policies.
- GitHub CI and community templates.

### Changed

- Dora workflows use `FORGE_RUNTIME_ROOT` and `FORGE_RUNTIME_BIN` instead of a
  fixed workspace layout.
- Public documentation no longer contains internal repository or machine paths.
- GLB documentation reflects the self-contained assets currently delivered.

### Safety

- Documented low-speed first-motion checks, emergency-stop requirements,
  playback unit validation, and the torque-enabled disconnect behavior.

[1.1.3]: https://github.com/Forgelab-Robotics/adapter-robot-piper/releases/tag/v1.1.3
