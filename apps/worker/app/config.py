from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SAMPLES_DIR = str((Path(__file__).resolve().parent.parent / "samples"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PDF_FORMS_")

    job_ttl_seconds: int = 3600
    max_upload_bytes: int = 25 * 1024 * 1024
    max_batch_files: int = 100
    artifact_secret: str = "dev-secret-change-me"
    pdfcpu_path: str = "pdfcpu"
    qpdf_path: str = "qpdf"
    node_sidecar_url: str = "http://localhost:8787"
    samples_dir: str = DEFAULT_SAMPLES_DIR


settings = Settings()
