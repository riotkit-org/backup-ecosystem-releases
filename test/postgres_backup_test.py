import typing
import os
from framework import ClientServerBase
from framework.postgresbase import PostgresTestingHelper


TESTS_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/test"


class PostgresBackupTest(ClientServerBase):
    def __init__(self, methodName: str):
        super().__init__(methodName)

        self.postgres = PostgresTestingHelper(
            host="127.0.0.1",
            port=8053,
            user="riotkit",
            password="warisbad",
            db_name="backuprepository",
        )

    def test_postgres_backup_and_restore_with_internal_template(self):
        self._run_simple_test(pg_template="pg15", template_type="internal")

    def test_postgres_backup_and_restore_with_template_from_crd(self):
        def prepare():
            self.apply_manifests(TESTS_DIR + "/data/postgres_backup_test/pg15-test-template.yaml")

        self._run_simple_test(pg_template="pg15-test-template", template_type="ClusterBackupProcedureTemplate", prepare=prepare)

    def _run_simple_test(self, pg_template: str, template_type: str, prepare: typing.Callable = None):
        with self.in_dir("test/data/postgres_backup_test"), \
                self.kubernetes_namespace("subject"), \
                self.show_logs_on_failure():
            # deploy a test postgres instance
            self.skaffold_deploy()
            self.port_forward(local_port=8053, remote_port=5432,
                              pod_label="app.kubernetes.io/name=postgresql",
                              ns="subject")

            # ------------------------
            # Prepare server instance
            # ------------------------
            self.server.i_create_a_user(
                name="international-workers-association",
                email="example@iwa-ait.org",
                password="cnt1936",
            )
            self.server.i_create_a_collection(
                name="iwa-ait",
                description="IWA-AIT website files",
                filename_template="iwa-ait-${version}.tar.gz",
                max_backups_count=5,
                max_one_version_size="1M",
                max_collection_size="10M",
                strategy_name="fifo"
            )
            access_token = self.server.i_login(
                username="international-workers-association",
                password="cnt1936"
            )

            # -------------------------------------------------------------------------------
            # Prepare data of our SUBJECT - Postgres DB we want to Backup & Modify & Restore
            # -------------------------------------------------------------------------------

            if prepare:
                prepare()

            # Prepare the subject of our backup
            # language=postgresql
            self.postgres.query("""
                CREATE TABLE IF NOT EXISTS movies (
                    id 	INT PRIMARY KEY,
                    name VARCHAR(64) NOT NULL
                );
                INSERT INTO public.movies (id, name) VALUES (1, 'Ni dieu ni maitre, une historie de l"anarchisme');
                COMMIT;
            """)

            # Create a backup definition
            self.client.i_schedule_a_backup(
                name="app1",
                operation="backup",
                cronjob_enabled=True,
                schedule_every="00 02 * * *",
                collection_id="iwa-ait",
                access_token=access_token,
                template_name=pg_template,
                template_kind=template_type,
                email="example@iwa-ait.org",
                # language=yaml
                template_vars=f"""
                    Params:
                        hostname: test-postgresql.subject.svc.cluster.local
                        port: 5432
                        db: backuprepository
                        user: riotkit
                        password: "warisbad"
                    
                    Repository:
                        url: "http://server-backup-repository-server.backups.svc.cluster.local:8080"
                        encryptionKeyPath: "/mnt/secrets/gpg-key"
                        passphrase: ""
                        recipient: "example@iwa-ait.org"
                        collectionId: "iwa-ait"
                """,
            )

            # Run backup action immediately
            self.client.i_request_backup_action(
                kind_type="Job",
                name="iwa-ait-v1-backup",
                action="backup",
                ref="app1",
            )
            assert self.client.backup_has_status(name="iwa-ait-v1-backup", expected=True)

            # Add EXTRA ROW that would be reverted after the backup was kubectlrestored
            self.postgres.query("""
                INSERT INTO public.movies (id, name) VALUES (2, 'Some-wrong-title');
                COMMIT;
            """)

            self.assertEqual([('Ni dieu ni maitre, une historie de l"anarchisme',), ('Some-wrong-title',)],
                             self.postgres.select("SELECT name FROM public.movies"))

            # Try to restore
            self.client.i_request_backup_action(
                name="iwa-ait-v1-restore",
                action="restore",
                ref="app1",
            )
            assert self.client.backup_has_status(name="iwa-ait-v1-restore", expected=True)

            # Check
            self.assertEqual([('Ni dieu ni maitre, une historie de l"anarchisme',)],
                             self.postgres.select("SELECT name FROM public.movies"))
