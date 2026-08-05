from utils.panda_parser import parse_panda_text


TABBED = (
    "Adobe Acrobat\tAdobeAcrobatDCCoreApp_26\t03/08/2026\t-\t26.1.0.0\n"
    "Adobe Acrobat (64-bit)\tAdobe\t03/08/2026\t2,5 GB\t26.001.21771\n"
)

VERTICAL = (
    "Adobe Acrobat\n"
    "AdobeAcrobatDCCoreApp_26\n"
    "03/08/2026\n"
    "-\n"
    "26.1.0.0\n"
    "Adobe Acrobat (64-bit)\n"
    "Adobe\n"
    "03/08/2026\n"
    "2,5 GB\n"
    "26.001.21771\n"
)


class TestPandaParser:
    def test_parsea_tabulado(self):
        result = parse_panda_text(TABBED)
        assert result.ok
        assert result.mode == "tabbed"
        assert len(result.rows) == 2
        assert result.rows[0]["nombre"] == "Adobe Acrobat"
        assert result.rows[1]["tamano"] == "2,5 GB"

    def test_parsea_vertical_en_bloques_de_cinco(self):
        result = parse_panda_text(VERTICAL)
        assert result.ok
        assert result.mode == "vertical"
        assert len(result.rows) == 2
        assert result.rows[0]["fabricante"] == "AdobeAcrobatDCCoreApp_26"
        assert result.rows[0]["version"] == "26.1.0.0"
        assert result.rows[1]["nombre"] == "Adobe Acrobat (64-bit)"

    def test_vertical_incompleto_da_error(self):
        result = parse_panda_text("App\nEditor\n01/01/2026\n")
        assert not result.ok
        assert result.errors
        assert "5 lineas" in result.errors[0].message

    def test_tabulado_con_columnas_de_mas_da_error(self):
        result = parse_panda_text("App\tEditor\t01/01/2026\t1 MB\t1.0\tEXTRA\n")
        assert not result.ok
        assert "5 columnas" in result.errors[0].message
