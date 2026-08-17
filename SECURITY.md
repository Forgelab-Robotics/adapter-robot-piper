# Security policy

## Supported versions

Security fixes are applied to the latest release on the default branch.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for this repository. Do not open a
public issue for credentials, remote-control vulnerabilities, unsafe motion
paths, denial of emergency-stop behavior, or other findings that could endanger
people or equipment.

Include:

- affected version or commit;
- required hardware and firmware, if applicable;
- reproduction steps that avoid physical motion where possible;
- expected impact;
- suggested mitigation.

Maintainers will acknowledge a report through GitHub, assess severity, and
coordinate disclosure after a fix or mitigation is available.

For an immediate physical hazard, use the manufacturer's emergency stop and
disconnect the system according to the hardware manual before reporting.

## Scope

Security reports may cover the Python package, Dora node, CAN integration,
configuration parsing, recorded-action playback, build scripts, and bundled
robot assets. Vulnerabilities in third-party dependencies should also be
reported to their upstream maintainers.
