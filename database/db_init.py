import os

from database.database_connect import database_connect, with_transaction
from database.database_queries import init_vector, init_messages, init_documents


if __name__ == "__main__":

    from dotenv import load_dotenv
    load_dotenv()

    conn = database_connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    with with_transaction(conn=conn) as cursor:
        init_vector(cursor)
        init_messages(cursor)
        init_documents(cursor)

    print("DB inited")
