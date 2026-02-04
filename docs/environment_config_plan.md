# Environment & Infrastructure Implementation Plan

This document outlines the tasks required to standardize Oponn's execution environments (Dev, Staging, Prod) and ensure robust test isolation using Testcontainers.

## 1. Environment Specifications

| Feature | Development (`make dev`) | Staging (`make staging`) | Production (`make prod`) |
| :--- | :--- | :--- | :--- |
| **Database** | In-Memory (SQLite/Dict) | Postgres (LocalStack/Docker) | Postgres (RDS/External) |
| **KMS** | No-op / Local Key | LocalStack KMS | AWS KMS |
| **Redis** | In-Memory Fallback | Redis (LocalStack/Docker) | Redis (ElastiCache/External) |
| **Auth** | Mock Sign-in | Mock Sign-in | Real OAuth (Google/GitHub) |
| **Processes** | Single (Hot-reload) | Multiple (Gunicorn) | Multiple (Gunicorn) |
| **Logging** | Pretty-print | Pretty-print | JSON |

---

## 2. Component Breakdown & Task List

### A. Configuration & Settings (`src/config.py`)
- [x] **Fix Staging Validator**: Allow `localstack_endpoint` in Staging, but keep it forbidden in Production.
- [x] **Infrastructure Toggles**: Ensure `is_in_memory` property correctly triggers based on `database_url` and `redis_url` being `None`.
- [x] **Auth Toggle**: Add `use_mock_auth: bool` to `BaseAppSettings`.
- [x] **Logging Toggle**: Add `log_format: Literal["pretty", "json"]` to `BaseAppSettings`.

### B. Crypto & KMS (`src/services/kms_provider.py`)
- [x] **Implement `LocalMasterKeyProvider`**:
    - *Option B (Local Key)*: Uses a local static Tink keyset to exercise the full encryption/decryption pipeline without external dependencies.
- [x] **Dependency Injection (`src/dependencies.py`)**: Update `get_crypto_service` to return `LocalMasterKeyProvider` if `OPONN_KMS_KEY_ID` is missing in Dev/Test.

### C. Logging (`src/logging_conf.py`)
- [x] **Dynamic Renderer**: Update `configure_logging` to use `settings.log_format`.

### D. Authentication (`src/services/auth_service.py` & `src/routes/auth.py`)
- [x] **Mock Provider**: Implemented `use_mock_auth` toggle to bypass real OAuth providers in Dev/Staging.

### E. Test Infrastructure (`tests/conftest.py`)
- [x] **Testcontainers Integration**: Added `PostgresContainer`, `RedisContainer`, and `LocalStackContainer` for session-scoped test isolation.
- [x] **Fixture Updates**: Verified settings reload and environment variable injection for tests.

### F. CLI & Process Management (`manage.py` & `Makefile`)
- [x] **Staging Workers**: Enabled Gunicorn workers for Staging and Production.
- [x] **Environment Variable Loading**: Updated `manage.py` to use `load_dotenv(..., override=True)` for environment-specific prioritization.

---

## 3. Lessons Learned & Technical Details

### Tink AEAD Registration Locality
**Issue**: A `500 Error` was triggered when trying to create a ballot or view the dashboard: `No manager for type type.googleapis.com/google.crypto.tink.AesGcmKey has been registered`.
**Root Cause**: Google Tink requires an explicit registration call (`tink.aead.register()`) before any key managers or primitives can be used. In our DI setup, `LocalMasterKeyProvider` was initialized and attempted to create a `new_keyset_handle` inside its `__init__`. This happened *before* the `CryptoService` (which previously held the registration call) was instantiated.
**Solution**: Moved `tink.aead.register()` into the `LocalMasterKeyProvider.__init__` and kept it in `CryptoService` to ensure that regardless of the entry point or provider type, the global Tink registry is populated before use.

### Environment Variable Masking & Prioritization
**Issue**: `make dev` was attempting to connect to a real Postgres instance even though `.env.development` had `DATABASE_URL=` (empty).
**Root Cause**: Process-level environment variables (those already in `os.environ`) always take precedence over values in `.env` files when using Pydantic `BaseSettings`. By default, `manage.py` was loading the base `.env` file first. If `.env` contained a database URL, that variable was locked into the process memory. Subsequent attempts to load `.env.development` would not overwrite the already-set environment variable.
**Solution**: Updated `manage.py` to load `.env` files in a specific order with the `override=True` flag:
1. Load `.env` (the global base).
2. Load `.env.{OPONN_ENV}` with `override=True`. This explicitly forces the process environment to take the value from the specific file, allowing us to "clear" variables (set them to empty strings) to trigger zero-config/in-memory modes.

### LocalStack Credential Fallbacks in Staging

**Issue**: Staging environment failed with `botocore.exceptions.NoCredentialsError: Unable to locate credentials`.

**Root Cause**: The `AwsKmsMasterKeyProvider` was treating Staging as "Production" for the purpose of credential validation. While Staging mirrors Production in architecture (using real Redis/Postgres/Multiple Workers), it often uses LocalStack for KMS which requires dummy credentials (`test`/`test`) if real ones aren't provided.

**Solution**: Refined the `is_production` flag in the dependency injector. Now, the provider only strictly requires external credentials when `OPONN_ENV=production`. In Staging, it allows the fallback to LocalStack-compatible dummy credentials if `AWS_ACCESS_KEY_ID` is missing from the environment.
