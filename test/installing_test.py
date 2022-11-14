from framework import controller_repository_at_revision, EndToEndTestBase


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
        ns = "backup-maker-operator"

        with controller_repository_at_revision(self.release["CONTROLLER_VERSION"]):
            with self.kubernetes_namespace(ns):
                self.apply_manifests("config/crd/bases")
                self.skaffold_deploy()

                assert self.has_pod_with_label_present("app=backup-maker-operator")
