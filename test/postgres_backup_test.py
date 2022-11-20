from framework import ClientServerBase
from framework.postgresbase import PostgresTestingHelper


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

    def test_postgres_backup_and_restore(self):
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
                template_name="pg13",
                email="example@iwa-ait.org",
                template_vars=f"""
                    Params:
                        hostname: postgres-postgresql.subject.svc.cluster.local
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

            assert self.client.backup_has_completed_status(name="iwa-ait-v1-backup")

            # Add EXTRA ROW that would be reverted after the backup was restored
            self.postgres.query("""
                INSERT INTO public.movies (id, name) VALUES (2, 'Some-wrong-title');
                COMMIT;
            """)

            # Try to restore
            # self.client.i_request_backup_action(
            #     name="iwa-ait-v1-restore",
            #     action="restore",
            #     ref="app1",
            # )

            # Check
            # assert self.pg_query("SELECT ...") == "anarchist movement"
