from mock import patch
import pytest
import bumper
import os
import subprocess
import tempfile
from pathlib import Path
import shutil


def mock_subrun(*args):
    return args


@patch("bumper.start")
def test_argparse(mock_start):
    bumper.ca_cert = "tests/test_certs/ca.crt"
    bumper.server_cert = "tests/test_certs/bumper.crt"
    bumper.server_key = "tests/test_certs/bumper.key"

    bumper.main(["--debug"])
    assert bumper.bumper_debug == True
    assert mock_start.called == True

    bumper.main(["--listen", "127.0.0.1"])
    assert bumper.bumper_listen == "127.0.0.1"
    assert mock_start.called == True

    bumper.main(["--announce", "127.0.0.1"])
    assert bumper.bumper_announce_ip == "127.0.0.1"
    assert mock_start.called == True

    bumper.main(["--debug", "--listen", "127.0.0.1", "--announce", "127.0.0.1"])
    assert bumper.bumper_debug == True
    assert bumper.bumper_announce_ip == "127.0.0.1"
    assert bumper.bumper_listen == "127.0.0.1"
    assert mock_start.called == True


@patch("bumper.first_run")
def test_main(mock_firstrun):
    bumper.ca_cert = "sf"
    bumper.main()
    assert mock_firstrun.called == True
    bumper.ca_cert = "tests/test_certs/ca.crt"


def test_generate_certs_script(tmp_path):

    cert_creation_dir: Path = Path("create_certs")
    certs_dir: Path = Path(tmp_path)

    certs_dir.mkdir(parents=True, exist_ok=True)

    script_path: Path = cert_creation_dir / "create_cert.sh"

    certs_dir.absolute()

    path_certs = str(certs_dir) + "/"

    cmd = [str(script_path), path_certs]

    result = subprocess.Popen(cmd,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE)
    stdout, stderr = result.communicate()
    print("STDOUT:", stdout)
    print("STDERR:", stderr)

    assert result.returncode == 0, f"Script failed with return code {result.returncode}"

    expected_files = [
        "ca.key", "ca.csr", "ca.crt",
        "bumper.key", "bumper.csr", "bumper.crt"
    ]

    for filename in expected_files:
        file_path = certs_dir / filename
        assert file_path.exists(), f"Expected file {filename} not found in {certs_dir}"

    assert True
