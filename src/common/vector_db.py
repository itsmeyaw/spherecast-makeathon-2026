import os
import psycopg2


def get_connection():
    sslmode = os.environ.get("PGVECTOR_SSLMODE", "verify-full")
    sslrootcert = os.environ.get("PGVECTOR_SSLROOTCERT", "")
    return psycopg2.connect(
        host=os.environ["PGVECTOR_HOST"],
        port=int(os.environ.get("PGVECTOR_PORT", "5432")),
        dbname=os.environ["PGVECTOR_DB"],
        user=os.environ["PGVECTOR_USER"],
        password=os.environ["PGVECTOR_PASSWORD"],
        sslmode=sslmode,
        **({"sslrootcert": sslrootcert} if sslrootcert else {}),
    )
