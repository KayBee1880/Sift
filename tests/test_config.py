from app.config import Settings
from app.db.models import EMBEDDING_DIMENSION


def test_database_url_is_built_from_individual_fields():
    settings = Settings(
        postgres_user="testuser",
        postgres_password="testpass",
        postgres_db="testdb",
        postgres_host="testhost",
        postgres_port=1234,
    )
    assert settings.database_url == "postgresql+psycopg://testuser:testpass@testhost:1234/testdb"


def test_settings_embedding_dimension_matches_schema_dimension():
    # app/db/models.py hardcodes EMBEDDING_DIMENSION separately from Settings on purpose
    # (see that file's walkthrough), so nothing enforces they stay equal except this test.
    settings = Settings()
    assert settings.embedding_dimension == EMBEDDING_DIMENSION
