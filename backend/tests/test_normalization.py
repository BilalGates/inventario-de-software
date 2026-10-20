from app.services.normalization import classify, hostname_key, name_key, publisher_key, serial_key


def test_name_key_is_conservative():
    assert name_key("Microsoft  365 Apps®") == name_key("microsoft 365 apps")
    # Productos distintos con nombres parecidos NO se unifican.
    assert name_key("Microsoft Visual C++ 2015-2022 Redistributable (x64)") != name_key(
        "Microsoft Visual C++ 2015-2022 Redistributable (x86)")
    assert name_key("Adobe Acrobat Reader") != name_key("Adobe Acrobat")


def test_name_key_strips_trailing_version_only_when_equal():
    assert name_key("7-Zip 23.01", "23.01") == name_key("7-Zip 24.08", "24.08") == "7-zip"
    assert name_key("Notepad++ 8.6", "8.5") == "notepad++ 8.6"
    assert name_key("Anaconda3 2022.05 (Python 3.9.12 64-bit)", "2022.05") == "anaconda3 2022.05 (python 3.9.12 64-bit)"


def test_publisher_key_removes_corporate_suffixes():
    assert publisher_key("Microsoft Corporation") == publisher_key("Microsoft Corp.") == "microsoft"
    assert publisher_key("Anaconda, Inc.") == "anaconda"
    assert publisher_key(None) == ""


def test_classify():
    assert classify("Microsoft Visual C++ 2015-2022 Redistributable (x64) - 14.38") == "runtime"
    assert classify("Intel(R) Wireless Bluetooth(R) Driver") == "driver"
    assert classify("Security Update for Windows (KB5034441)") == "update"
    assert classify("Google Chrome") == "application"


def test_serial_and_hostname_keys():
    assert serial_key("To be filled by O.E.M.") is None
    assert serial_key("0000000") is None
    assert serial_key(" pf3abc12 ") == "PF3ABC12"
    assert hostname_key("pc-001.asserta.local") == "PC-001"


def test_certificate_subject_publishers():
    from app.services.normalization import clean_publisher
    dn = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"
    assert clean_publisher(dn) == "Microsoft Corporation"
    assert publisher_key(dn) == publisher_key("Microsoft Corporation")
    assert clean_publisher('CN="Pulse Secure, LLC"", OU=Engineering-2021, O=""Pulse Secure, LLC""') == "Pulse Secure, LLC"
    assert clean_publisher("CN=1B347D37-7DB7-4426-8262-A4E441AA2D89") is None  # GUID de la Store sin nombre
    assert clean_publisher("CN=1B347D37-7DB7-4426-8262-A4E441AA2D89, O=Contoso Ltd") == "Contoso Ltd"
    assert clean_publisher("Google LLC") == "Google LLC"


def test_windows_packages_are_system_components():
    dn = "CN=Microsoft Corporation, O=Microsoft Corporation, C=US"
    assert classify("Microsoft.BingNews", dn) == "system_component"
    assert classify("3A48D7FC-AEE2-4CBC-91D1-0007951B8006", "CN=Contoso") == "system_component"
    assert classify("MSTeams", dn) == "application"  # app MSIX con nombre normal
    assert classify("Node.js", "Node.js Foundation") == "application"  # puntos, pero no es un paquete
