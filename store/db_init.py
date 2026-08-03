import os

from db_utils import database_connect, create_table_messages, drop_table_messages

from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":

    drop_table_messages(conn=database_connect(
        host=os.getenv("POSTGRES_HOST"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    ))

    create_table_messages(conn=database_connect(
        host=os.getenv("POSTGRES_HOST"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    ))

    print("DB inited")
