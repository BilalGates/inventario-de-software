"""Tests de normalización de nombres y de versiones-como-texto (FASE 6)."""
import pytest

from utils.normalizer import clean_version, normalize_nombre, version_changed


class TestNormalizeNombre:
    def test_uppercase_y_trim(self):
        assert normalize_nombre("  Adobe   Acrobat  ") == "ADOBE ACROBAT"

    def test_colapsa_espacios(self):
        assert normalize_nombre("7-Zip\t23.01   (x64)") == "7-ZIP 23.01 (X64)"

    def test_conserva_parentesis_y_guiones(self):
        # No deben eliminarse: forman parte del nombre.
        assert normalize_nombre("Adobe Acrobat (64-bit)") == "ADOBE ACROBAT (64-BIT)"

    def test_none_o_vacio(self):
        assert normalize_nombre(None) == ""
        assert normalize_nombre("") == ""


class TestCleanVersionPreservaTexto:
    # Estas versiones DEBEN conservarse como texto, sin convertirse a float/int.
    @pytest.mark.parametrize(
        "raw",
        ["26.001.21563", "7.4.2.1737", "2.10", "2.9", "16.0.14332", "ad 9.0.10", "2022.05"],
    )
    def test_versiones_se_preservan_como_texto(self, raw):
        result = clean_version(raw)
        assert result == raw
        assert isinstance(result, str)

    def test_no_pierde_ceros_ni_puntos(self):
        # "2.10" != "2.1": el punto y el cero son significativos.
        assert clean_version("2.10") != clean_version("2.1")
        assert clean_version("2.10") == "2.10"

    def test_entero_de_pandas_se_convierte_a_str_sin_decimales(self):
        assert clean_version(2025) == "2025"
        assert clean_version(2025.0) == "2025"
        assert isinstance(clean_version(2025.0), str)

    def test_valores_vacios_o_marcadores_devuelven_none(self):
        for raw in (None, "", "-", "–", "nan", "NaN", "None"):
            assert clean_version(raw) is None

    def test_nan_float(self):
        assert clean_version(float("nan")) is None


class TestVersionChanged:
    def test_misma_version_no_cambia(self):
        assert version_changed("1.0", "1.0") is False

    def test_version_distinta_cambia(self):
        assert version_changed("1.0", "1.1") is True

    def test_sin_referencia_previa_y_con_nueva_cambia(self):
        assert version_changed(None, "1.0") is True

    def test_nueva_vacia_no_cambia(self):
        assert version_changed("1.0", None) is False
        assert version_changed("1.0", "-") is False

    def test_no_usa_comparacion_lexicografica(self):
        # El bug original (str ">") trataba "9.0" como mayor que "10.0".
        # version_changed solo mira igualdad: ambos casos son "cambio".
        assert version_changed("9.0", "10.0") is True
        assert version_changed("10.0", "9.0") is True
        # Y NO debe reportar cambio cuando son idénticas aunque "parezcan" raras.
        assert version_changed("26.001.21563", "26.001.21563") is False
