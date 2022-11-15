import contextlib
import os

from .endtoendbase import EndToEndTestBase, cloned_repository_at_revision


class ClientServerBase(EndToEndTestBase):

    @contextlib.contextmanager
    def client_and_server_deployed(self):
        pwd = os.getcwd()
        server_ver = self.release["SERVER_VERSION"]
        client_ver = self.release["CONTROLLER_VERSION"]

        # server
        with cloned_repository_at_revision("https://github.com/riotkit-org/backup-repository", server_ver):
            with self.kubernetes_namespace("backups"):
                self.skaffold_deploy()

                # client
                with cloned_repository_at_revision("https://github.com/riotkit-org/backup-maker-operator", client_ver):
                    with self.kubernetes_namespace("backup-maker-operator"):
                        self.apply_manifests("config/crd/bases")
                        self.skaffold_deploy()
                        os.chdir(pwd)
                        yield
