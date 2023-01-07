import contextlib
import dataclasses
import os
import subprocess as sp
import textwrap
import time
from json import loads as json_loads

import requests
from .endtoendbase import EndToEndTestBase, cloned_repository_at_revision


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
             
        """, ns="backups")
        self._parent.apply_yaml(f"""
        ---
        apiVersion: v1
        kind: Secret
        metadata:
            name: {name}-secret
        data:
            password: {encoded_password}
        """, ns="backups")

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
        """, ns="backups")

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
        """, ns="backups")

    def i_login(self, username: str, password: str) -> str:
        response = requests.post(self._url + "/api/stable/auth/login", json={
            "username": username,
            "password": password,
        })
        body = response.json()
        return body["data"]["token"]


@dataclasses.dataclass
class _Client:
    ns: str
    _parent: EndToEndTestBase

    def i_schedule_a_backup(self, name: str, operation: str, email: str, cronjob_enabled: bool, schedule_every: str,
                            collection_id: str, access_token: str, template_name: str, template_vars: str, template_kind: str):
        self._parent.apply_yaml(ns=self.ns, yaml=f"""
        ---
        apiVersion: v1
        kind: Secret
        metadata:
            name: backup-keys
            namespace: {self.ns}
        stringData:
            passphrase: ""
            token: "{access_token}"
        """)

        self._parent.apply_yaml(ns=self.ns, yaml=f"""
        ---
        apiVersion: riotkit.org/v1alpha1
        kind: ScheduledBackup
        metadata:
            name: {name}
            namespace: {self.ns}
        spec:
            operation: {operation}
            cronJob:
                enabled: {str(cronjob_enabled).lower()}
                scheduleEvery: "{schedule_every}"
            collectionId: {collection_id}
            gpgKeySecretRef:
                createIfNotExists: true
                email: {email}
                passphraseKey: passphrase
                privateKey: private
                publicKey: public
                secretName: backup-keys
            tokenSecretRef:
                secretName: backup-keys
                tokenKey: token
            templateRef:
                kind: {template_kind}
                name: {template_name}
        
            vars: |
{textwrap.indent(template_vars, "                ")}
            varsSecretRef: {"{}"}
        """)

    def i_request_backup_action(self, name: str, action: str, ref: str, kind_type: str = "Job"):
        self._parent.apply_yaml(ns=self.ns, yaml=f"""
        ---
        apiVersion: riotkit.org/v1alpha1
        kind: RequestedBackupAction
        metadata:
            name: {name}
            namespace: {self.ns}
        spec:
            kindType: {kind_type}
            action: {action}
            scheduledBackupRef:
                name: {ref}
        """)

    def backup_has_status(self, name: str, expected: bool, kubectl_timeout: int = 10,
                          retries_left: int = 30, wait_time: int = 1) -> bool:
        try:
            cmd = ["get", "requestedbackupaction", name, "-o", "json"]
            out = json_loads(self._parent.kubectl(cmd).lower().strip().strip("'"))
            print("backup_has_status = " + str(out['status']))

            healthy = out['status']['healthy'] is True
            any_resource_running = False
            for resource in out['status']['childrenresourceshealth']:
                if resource['running']:
                    any_resource_running = True

            # CONDITION: backup/restore needs to be finished and HEALTHY
            result = not any_resource_running and healthy

            if result != expected and retries_left > 0:
                time.sleep(wait_time)
                return self.backup_has_status(name, expected, kubectl_timeout, retries_left - 1)

            return result

        except KeyError:
            if retries_left > 0:
                time.sleep(wait_time)
                return self.backup_has_status(name, expected, kubectl_timeout, retries_left - 1)
            raise
        except sp.CalledProcessError:
            if retries_left > 0:
                time.sleep(wait_time)
                return self.backup_has_status(name, expected, kubectl_timeout, retries_left - 1)
            raise


class ClientServerBase(EndToEndTestBase):
    last_test_class: str = ""
    server: _Server
    client: _Client

    @classmethod
    def setUpClass(cls) -> None:
        EndToEndTestBase.setUpClass()

    def setUp(self) -> None:
        EndToEndTestBase.setUp(self)
        self.server = _Server(self, "http://127.0.0.1:8070", ns="backups")
        self.client = _Client(_parent=self, ns="subject")

        # --- hack: deploy only once, before first test starts
        current_test_class = self.__class__.__name__
        if ClientServerBase.last_test_class != current_test_class:
            self._deploy_client_and_server(delete=False, retries_left=5)
            self.port_forward(local_port=8070, remote_port=8080, ns="backups",
                              pod_label="app.kubernetes.io/name=backup-repository-server")
            ClientServerBase.last_test_class = current_test_class
        # --- end of hack

    @contextlib.contextmanager
    def show_logs_on_failure(self):
        try:
            yield
        except:
            self.logs(pod_label="app.kubernetes.io/name=backup-repository-server", ns="backups", allow_failure=True)
            self.logs(pod_label="app=backup-maker-controller", ns="backup-maker-controller", allow_failure=True)
            raise

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
                    self.skaffold_deploy(skip_when=os.getenv("SKIP_SERVER_INSTALL") == "true")

                    # client
                    with cloned_repository_at_revision("https://github.com/riotkit-org/backup-maker-controller",
                                                       client_ver):
                        with self.kubernetes_namespace("backup-maker-controller", persistent=not delete):
                            self.apply_manifests("config/crd/bases")
                            self.skaffold_deploy(skip_when=os.getenv("SKIP_CLIENT_INSTALL") == "true")
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
