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
