import os
import subprocess

import requests

from .endtoendbase import EndToEndTestBase, cloned_repository_at_revision, run


class _Server:
    _parent: EndToEndTestBase
    _url: str

    def __init__(self, parent: EndToEndTestBase, url: str):
        self._parent = parent
        self._url = url

    def i_create_a_user(self, name: str, email: str, password: str):
        encoded_password = subprocess.check_output(["br", "--encode-password", password], stderr=subprocess.STDOUT) \
            .strip().decode('utf-8')

        self._parent.apply_yaml(f"""
        ---
        apiVersion: backups.riotkit.org/v1alpha1
        kind: BackupUser
        metadata:
            name: {name}
        spec:
            # best practice is to set this e-mail to same e-mail as GPG key owner e-mail (GPG key used on client side to encrypt files)
            email: {email}
            deactivated: false
            organization: "Riotkit"
            about: "Some user"
            passwordFromRef: 
                name: {name}-secret
                entry: password
            #restrictByIP:
            #    - 1.2.3.4
            roles:
                - systemAdmin
             
        """)
        self._parent.apply_yaml(f"""
        ---
        apiVersion: v1
        kind: Secret
        metadata:
            name: {name}-secret
        stringData:
            password: {encoded_password}
        """)

    def i_create_a_collection(self, name: str, description: str, filename_template: str, max_backups_count: int,
                              max_one_version_size: str, max_collection_size: str, strategy_name: str):
        self._parent.apply_yaml("""
        ---
        apiVersion: v1
        kind: Secret
        metadata:
            name: backup-repository-collection-secrets
        type: Opaque
        data:
            # to generate: use echo -n "admin" | sha256sum
            iwa-ait: "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
        """)

        self._parent.apply_yaml(f"""
        ---
        apiVersion: backups.riotkit.org/v1alpha1
        kind: BackupCollection
        metadata:
            name: {name}
        spec:
            description: "{description}"
            filenameTemplate: {filename_template}
            maxBackupsCount: {max_backups_count}
            maxOneVersionSize: "{max_one_version_size}"
            maxCollectionSize: "{max_collection_size}"
            #windows:
            #    - from: "*/30 * * * *"
            #      duration: 30m
            strategyName: {strategy_name}
            strategySpec: {"{}"}
            healthSecretRef:
                name: backup-repository-collection-secrets
                entry: iwa-ait
            accessControl:
                - userName: admin
                  roles:
                      - collectionManager
        """)

    def i_generate_an_access_token(self, username: str, password: str) -> str:
        response = requests.get(self._url + "/api/stable/auth/login", json={
            "username": username,
            "password": password,
        })
        body = response.json()
        return body["data"]["token"]


class ClientServerBase(EndToEndTestBase):
    last_test_class: str = ""
    server: _Server

    @classmethod
    def setUpClass(cls) -> None:
        EndToEndTestBase.setUpClass()

    def setUp(self) -> None:
        EndToEndTestBase.setUp(self)
        self.server = _Server(self, "http://127.0.0.1:8070")

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

        # be bulletproof on CI, avoid random failures sacrificing execution time
        except:
            if retries_left > 0:
                self._deploy_client_and_server(delete=delete, retries_left=retries_left-1)
                return
            raise

    # ---
    #  End of technical methods
    # ---