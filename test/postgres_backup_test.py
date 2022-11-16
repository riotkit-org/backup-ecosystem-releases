from framework import ClientServerBase


class PostgresBackupTest(ClientServerBase):
    def test_postgres_backup_and_restore(self):
        with self.in_dir("test/data/postgres_backup_test"), \
                self.kubernetes_namespace("subject"):
            # deploy a test postgres instance
            self.skaffold_deploy()

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
            access_token = self.server.i_generate_an_access_token(
                username="international-workers-association",
                password="cnt1936"
            )

            print(access_token)

            # Prepare the subject of our backup
            # self.pg_query("CREATE TABLE ...")
            # self.pg_query("INSERT INTO ...")

            # Create a backup definition
            # self.client.i_schedule_a_backup()

            # Run backup action immediately
            # self.client.i_request_backup_action()

            # assert self.client.backup_has_completed_status(scheduled_backup_name="app1", version="v1")

            # Add EXTRA ROW that would be reverted after the backup was restored
            # self.pg_query("INSERT INTO ...")

            # Try to restore
            # self.client.i_request_backup_action()

            # Check
            # assert self.pg_query("SELECT ...") == "anarchist movement"
