Backup Ecosystem Releases
=========================

Backup Repository is a complex system with a set of repositories, for this reason there is a release repository that releases a set of components compatible with each other.

We perform there End-To-End tests for selected software configurations.

Versioning
----------

`main` branch always points to latest versions of Backup Repository components.
In order to make a release there is a release branch created, then tagged.

### Creating a new release

1. Create a new branch within a convention `release-x.y` (only up to major + minor)
2. Set desired component versions in `release.env` file
3. Tag with a target version `vx.y.z` (up to major + minor + patch)

Testing
-------

### Requirements

- Skaffold: v2.0.0+
- Docker
- K3d: ~v5.4.6 (k3s ~v1.24)
- Helm: v3
