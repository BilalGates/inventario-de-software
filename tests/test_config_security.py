"""Tests de la validación de seguridad de la conexión a BD (FASE 5)."""
import pytest

from config import (
    InsecureDatabaseConfigError,
    check_db_security,
    ensure_secure_db_config,
)


class TestCheckDbSecurity:
    def test_usuario_root_es_inseguro(self):
        issues = check_db_security({"user": "root", "password": "algo"})
        assert any("root" in issue for issue in issues)

    def test_password_vacia_es_insegura(self):
        issues = check_db_security({"user": "inventario_app", "password": ""})
        assert any("contraseña" in issue for issue in issues)

    def test_config_segura_no_tiene_problemas(self):
        assert check_db_security({"user": "inventario_app", "password": "secreta"}) == []


class TestEnsureSecureDbConfig:
    def test_bloquea_config_insegura_sin_flag(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_LOCAL_DB", raising=False)
        with pytest.raises(InsecureDatabaseConfigError):
            ensure_secure_db_config({"user": "root", "password": ""})

    def test_permite_con_flag_pero_advierte(self, monkeypatch):
        monkeypatch.setenv("ALLOW_INSECURE_LOCAL_DB", "true")
        with pytest.warns(UserWarning):
            ensure_secure_db_config({"user": "root", "password": ""})

    def test_config_segura_no_lanza(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_LOCAL_DB", raising=False)
        # No debe lanzar ni advertir.
        ensure_secure_db_config({"user": "inventario_app", "password": "secreta"})
