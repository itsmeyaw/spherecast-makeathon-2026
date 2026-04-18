import os
import psycopg2


def get_connection():
    return psycopg2.connect(
        host=os.environ["PGVECTOR_HOST"],
        port=int(os.environ.get("PGVECTOR_PORT", "5432")),
        dbname=os.environ["PGVECTOR_DB"],
        user=os.environ["PGVECTOR_USER"],
        password=os.environ["PGVECTOR_PASSWORD"],
    )
