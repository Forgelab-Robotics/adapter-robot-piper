# Third-party notices

The repository's original Python code, configuration, workflows, and
documentation are licensed under Apache License 2.0 unless a file or directory
states otherwise. The following bundled assets retain their upstream licenses.

## AgileX Piper MuJoCo model

- Paths: `assets/mjcf/piper_mujoco/`, `assets/glb/`, and `assets/usd/`
- Source: [MuJoCo Menagerie — AgileX Piper](https://github.com/google-deepmind/mujoco_menagerie/tree/main/agilex_piper)
- Copyright: Copyright (c) 2024 RosenYin
- License: MIT

The GLB and USD files are converted forms of the MuJoCo model and retain the
same upstream attribution. Local changes include control semantics, cameras,
relative paths, and format conversion. The MIT license text is available at
`assets/mjcf/piper_mujoco/LICENSE`.

## AgileX Piper URDF

- Paths: `assets/urdf/`
- Source: AgileX Robotics `piper_ros` / `piper_description` 1.0.0
- Copyright: Copyright (c) 2024 RosenYin
- License: MIT

The license text is available at
`assets/urdf/LICENSE.piper_ros-noetic`. The delivered URDF was adjusted to use
repository-relative mesh paths and to align frames with the MuJoCo model.

## Runtime dependencies

Python dependencies are not vendored into this repository. Their licenses are
provided by their respective distributions, including:

- `dora-rs`: MIT (according to the installed PyPI distribution metadata)
- `forge-common`, `forge-msgs`, `forge-robot`: see their PyPI distributions
- `piper-sdk`: MIT
- `python-can`: LGPL-3.0
- `PyYAML`: MIT
- `Typer`: MIT

Distributing a bundled executable, including a PyInstaller artifact, may create
additional license obligations beyond distributing this source repository.
Review all bundled dependency licenses before publishing binary releases.
