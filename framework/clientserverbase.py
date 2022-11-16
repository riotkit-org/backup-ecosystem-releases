import os

from .endtoendbase import EndToEndTestBase, cloned_repository_at_revision


class ClientServerBase(EndToEndTestBase):
    last_test_class: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        EndToEndTestBase.setUpClass()

    def setUp(self) -> None:
        EndToEndTestBase.setUp(self)

        # --- hack: deploy only once, before first test starts
        current_test_class = self.__class__.__name__
        if ClientServerBase.last_test_class != current_test_class:
            self._deploy_client_and_server(delete=False, retries_left=5)
            ClientServerBase.last_test_class = current_test_class
        # --- end of hack

    def _deploy_client_and_server(self, delete: bool = True, retries_left: int = 0):
        """
        Deploys Backup Repository (server) + Backup Maker Controller (client)
        on the Kubernetes cluster
        """
        pwd = os.getcwd()
        server_ver = self.release["SERVER_VERSION"]
        client_ver = self.release["CONTROLLER_VERSION"]

        # server
        try:
            with cloned_repository_at_revision("https://github.com/riotkit-org/backup-repository", server_ver):
                with self.kubernetes_namespace("backups", persistent=not delete):
                    self.skaffold_deploy()

                    # client
                    with cloned_repository_at_revision("https://github.com/riotkit-org/backup-maker-operator", client_ver):
                        with self.kubernetes_namespace("backup-maker-operator", persistent=not delete):
                            self.apply_manifests("config/crd/bases")
                            self.skaffold_deploy()
                            os.chdir(pwd)
                            yield

        # be bulletproof on CI, avoid random failures sacrificing execution time
        except:
            if retries_left > 0:
                self._deploy_client_and_server(delete=delete, retries_left=retries_left-1)
                return
            raise

    # ---
    #  End of technical methods
    #  Beginning of domain methods (actions and assertions)
    # ---

    def i_create_user(self, user_name: str):
        pass
