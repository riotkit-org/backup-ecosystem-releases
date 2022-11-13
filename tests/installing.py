from framework import controller_repository_at_revision, EndToEndTestBase, skaffold_deploy


class InstallingEndToEndTest(EndToEndTestBase):
    def test_controller_installs_and_not_crashes(self):
        """
        Perform a test installation of the Kubernetes controller using Helm via Skaffold
        See skaffold.yaml configuration in backup-maker-controller repository

        Steps:
          - Builds a docker image
          - Pushes to local registry at :5000 port
          - Deploys a Helm Chart "charts/" from subdirectory
        """

        with controller_repository_at_revision(self.release["CONTROLLER_VERSION"]):
            skaffold_deploy()
