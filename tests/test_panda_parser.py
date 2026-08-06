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

    def test_vertical_sin_tamano_ni_version_se_acepta(self):
        # Antes se exigian bloques exactos de 5 lineas. Ahora tamano y
        # version son opcionales y la fila se reconstruye por la fecha.
        result = parse_panda_text("App\nEditor\n01/01/2026\n")
        assert result.ok
        assert result.mode == "loose"
        assert len(result.rows) == 1
        assert result.rows[0]["nombre"] == "App"
        assert result.rows[0]["fabricante"] == "Editor"
        assert result.rows[0]["tamano"] is None
        assert result.rows[0]["version"] is None

    def test_pegado_sin_tabs_con_campos_ausentes(self):
        # Pegado real que perdio los tabuladores: la 1a fila no trae
        # tamano y la 2a no trae version, asi que el total de lineas no
        # es multiplo de 5.
        texto = (
            "Panda Endpoint Agent\nPanda Security S.L.U.\n07/05/2026\n1.25.03.0000\n"
            "MiniTool Partition Wizard Free 12\nMiniTool Software Limited\n06/03/2021\n126,4 MB\n"
            "Google Chrome\nGoogle LLC\n17/06/2026\n452,9 MB\n149.0.7827.155\n"
        )
        result = parse_panda_text(texto)
        assert result.ok
        assert result.mode == "loose"
        assert len(result.rows) == 3
        assert result.rows[0]["version"] == "1.25.03.0000"
        assert result.rows[0]["tamano"] is None
        assert result.rows[1]["tamano"] == "126,4 MB"
        assert result.rows[1]["version"] is None
        assert result.rows[2]["nombre"] == "Google Chrome"
        assert result.rows[2]["version"] == "149.0.7827.155"

    def test_version_con_fecha_dentro_no_parte_la_fila(self):
        # Los "Windows Driver Package" traen la version como
        # "11/14/2019 1.0.2.9". Esa fecha no debe separar filas ni
        # colarse en el nombre del programa siguiente.
        texto = (
            "Windows Driver Package - Policia (UMPass) SmartCard\n"
            "Direccion General de la Policia\n"
            "27/04/2021\n"
            "11/14/2019 1.0.2.9\n"
            "Xbox TCUI\n"
            "Microsoft\n"
            "05/02/2024\n"
            "1.24.10001.0\n"
        )
        result = parse_panda_text(texto)
        assert result.ok
        assert len(result.rows) == 2
        assert result.rows[0]["version"] == "11/14/2019 1.0.2.9"
        assert result.rows[1]["nombre"] == "Xbox TCUI"
        assert result.rows[1]["version"] == "1.24.10001.0"

    def test_lineas_de_ruido_no_rompen_las_filas(self):
        # Un pegado con formato deja separadores sueltos entre filas.
        texto = (
            "Spotify\nSpotify AB\n27/07/2026\n-\n1.2.94.583.g60394bd5\n"
            "|\n"
            "Xbox TCUI\nMicrosoft\n05/02/2024\n-\n1.24.10001.0\n"
        )
        result = parse_panda_text(texto)
        assert result.ok
        assert len(result.rows) == 2
        assert result.rows[0]["nombre"] == "Spotify"
        assert result.rows[1]["nombre"] == "Xbox TCUI"

    def test_sin_fechas_da_error(self):
        result = parse_panda_text("App\nEditor\n1.0\n")
        assert not result.ok
        assert result.errors
        assert "fechas" in result.errors[0].message

    def test_sin_editor_se_acepta_con_fabricante_vacio(self):
        # Un pegado con formato puede perder la celda del editor. Preferimos
        # conservar el programa (con fabricante desconocido) a descartarlo.
        result = parse_panda_text("SoloNombre\n01/01/2026\n1 MB\n1.0\n")
        assert result.ok
        assert len(result.rows) == 1
        assert result.rows[0]["nombre"] == "SoloNombre"
        assert result.rows[0]["fabricante"] is None
        assert result.rows[0]["tamano"] == "1 MB"

    def test_fecha_sin_nada_delante_da_error(self):
        # Si no hay ni nombre antes de la fecha, la fila es irrecuperable.
        result = parse_panda_text("01/01/2026\n1 MB\n1.0\n")
        assert not result.ok
        assert result.errors
        assert "nombre" in result.errors[0].message

    def test_tabulado_con_columnas_de_mas_da_error(self):
        result = parse_panda_text("App\tEditor\t01/01/2026\t1 MB\t1.0\tEXTRA\n")
        assert not result.ok
        assert "5 columnas" in result.errors[0].message
