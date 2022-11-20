import dataclasses

import psycopg2


@dataclasses.dataclass
class PostgresTestingHelper(object):
    db_name: str
    user: str
    host: str
    password: str
    port: int

    def query(self, query: str):
        cur = self.connect()
        cur.execute(query)

    def select(self, query: str):
        cur = self.connect()
        cur.execute(query)

        return cur.fetchall()

    def connect(self):
        conn = psycopg2.connect(
            f"dbname='{self.db_name}' user='{self.user}' host='{self.host}' password='{self.password}' port='{self.port}'")

        return conn.cursor()
