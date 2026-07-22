from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./auto160.db"
    secret_key: str = "dev-secret-key"
    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 60 * 24 * 7
    bootstrap_admin_email: str = "admin@auto160.com"
    bootstrap_admin_login: str = "admin"
    bootstrap_admin_name: str = "Auto160 Admin"
    bootstrap_admin_password: str = "admin12345"
    catalog_seed_csv_path: str = "app/data/catalog_u160_audi_bmw_mini.csv"
    avby_accounts_json_path: str = "data/avby_service_accounts.json"
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "auto160-media"
    s3_region: str = "us-east-1"
    s3_presign_expires_seconds: int = 3600
    public_site_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
