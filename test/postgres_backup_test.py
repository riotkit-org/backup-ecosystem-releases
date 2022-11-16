from framework import ClientServerBase


class PostgresBackupTest(ClientServerBase):
    def test_postgres_backup_and_restore(self):
        with self.in_dir("test/data/postgres_backup_test"), \
                self.kubernetes_namespace("db"):
            # deploy a test postgres instance
            self.skaffold_deploy()

            self.i_create_a_user(
                name="international-workers-association",
                email="example@iwa-ait.org",
                password="cnt1936",
            )

            # self.i_create_a_collection(
            #     name="",
            #     filenameTemplate=""
            # )
