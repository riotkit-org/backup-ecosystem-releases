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
3. Push and wait for tests to pass on GitHub Actions
4. Push a tag with a target version `vx.y.z` (up to major + minor + patch)
5. Create release notes including all components

Testing
-------

```bash
make test
```

### Requirements

The following requirements are automatically installed when using `make` to run tests.

- Skaffold: v2.0.0+
- Docker
- K3d: ~v5.4.6 (k3s ~v1.24)
- Helm: v3
- Pipenv
- Python 3.9+
- kubectl v1.24+
- kubens


### Advanced

#### Using backup-repository and backup-maker-operator from local directories instead of cloning during the tests.

```bash
rm .build/backup-maker-operator -rf
rm .build/backup-repository -rf
ln -s {backup-operator-path-there} $(pwd)/.build/backup-maker-operator
ln -s {backup-repository-path-there} $(pwd)/.build/backup-repository
```

Then run tests with:
```bash
export SKIP_GIT_PULL=true
```

#### Skipping installation of server and client

```bash
export SKIP_CLIENT_SERVER_INSTALL=true
```
