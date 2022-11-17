import os
import subprocess as sp
import requests
import re

from .endtoendbase import EndToEndTestBase, cloned_repository_at_revision, run


class _Server:
    _parent: EndToEndTestBase
    _url: str
    _ns: str

    def __init__(self, parent: EndToEndTestBase, url: str, ns: str):
        self._parent = parent
        self._url = url
        self._ns = ns

    def i_create_a_user(self, name: str, email: str, password: str):
        encoded_password = sp.check_output(["br", "--encode-password", password], stderr=sp.STDOUT) \
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
             
        """, ns=self._ns)
        self._parent.apply_yaml(f"""
        ---
        apiVersion: v1
        kind: Secret
        metadata:
            name: {name}-secret
        data:
            password: {encoded_password}
        """, ns=self._ns)

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
        response = requests.post(self._url + "/api/stable/auth/login", json={
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
        self.server = _Server(self, "http://127.0.0.1:8070", ns="backups")

        # --- hack: deploy only once, before first test starts
        current_test_class = self.__class__.__name__
        if ClientServerBase.last_test_class != current_test_class:
            self._deploy_client_and_server(delete=False, retries_left=5)
            self._port_forward(local_port=8070, remote_port=8080, ns="backups",
                               service_name="server-backup-repository-server")
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

    def _port_forward(self, local_port: int, remote_port: int, service_name: str, ns: str) -> None:
        try:
            existing = sp.check_output(["/bin/sh", "-c",
                                        f"ps aux | grep kube | grep forward "
                                        f"| grep '{local_port}:{remote_port}' | grep -v grep"])
            parsed = re.findall("([a-zA-Z0-9]+)\s+([0-9]+)", existing.decode('utf-8'))
            if len(parsed) > 0:
                sp.check_call(["kill", "-9", parsed[0][1]])
        except sp.CalledProcessError:
            pass

        sp.Popen(["kubectl", "port-forward", "-n", ns, f"service/{service_name}", f"{local_port}:{remote_port}"],
                 stdout=sp.DEVNULL)

    # ---
    #  End of technical methods
    # ---
