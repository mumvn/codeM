from app.database import connect, init_db


def test_init_db_creates_expected_articles_schema(tmp_path):
    database = tmp_path / "digest.db"
    init_db(database)
    connection = connect(database)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
    connection.close()
    assert columns == {"id", "title", "link", "pub_date", "category", "raw_description", "ai_summary"}
