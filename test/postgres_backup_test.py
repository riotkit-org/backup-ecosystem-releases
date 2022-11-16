from framework import ClientServerBase


class PostgresBackupTest(ClientServerBase):
    def test_postgres_backup_and_restore(self):
        with self.in_dir("test/data/postgres_backup_test"), \
                self.kubernetes_namespace("db"):

            # deploy a test postgres instance
            self.skaffold_deploy()
