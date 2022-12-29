from framework import cloned_repository_at_revision, EndToEndTestBase


class InstallingEndToEndTest(EndToEndTestBase):
    """
    Basic test checking only if the applications are installing from Helm Charts at all
    """

    def test_client_controller_installs_and_not_crashes(self):
        """
        Perform a test installation of the Kubernetes controller using Helm via Skaffold
        See skaffold.yaml configuration in backup-maker-controller repository

        Steps:
          - Builds a docker image
          - Pushes to local registry at :5000 port
          - Deploys a Helm Chart from "charts/" subdirectory
        """
        ns = "backup-maker-controller"

        with cloned_repository_at_revision("https://github.com/riotkit-org/backup-maker-controller",
                                           self.release["CONTROLLER_VERSION"]):

            with self.kubernetes_namespace(ns):
                self.apply_manifests("config/crd/bases")
                self.skaffold_deploy()

                assert self.has_pod_with_label_present("app=backup-maker-controller")

    def test_backup_repository_installs_and_not_crashes(self):
        """
        Performs installation
        """
        ns = "backups"

        with cloned_repository_at_revision("https://github.com/riotkit-org/backup-repository",
                                           self.release["SERVER_VERSION"]):

            with self.kubernetes_namespace(ns):
                self.skaffold_deploy()

                assert self.has_pod_with_label_present("app.kubernetes.io/name=backup-repository-server")
