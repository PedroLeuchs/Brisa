import ipaddress
import ssl

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID

from backend.tools.generate_mobile_certificate import generate


def test_mobile_certificate_is_limited_to_requested_private_ip(tmp_path):
    generate("192.168.1.5", tmp_path, False)
    ca = x509.load_pem_x509_certificate((tmp_path / "brisa-ca.crt").read_bytes())
    server = x509.load_pem_x509_certificate((tmp_path / "brisa-server.crt").read_bytes())
    key = serialization.load_pem_private_key((tmp_path / "brisa-server.key").read_bytes(), password=None)

    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    assert server.issuer == ca.subject
    server.verify_directly_issued_by(ca)
    assert server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(
        x509.IPAddress
    ) == [ipaddress.ip_address("192.168.1.5")]
    assert server.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value == x509.ExtendedKeyUsage(
        [ExtendedKeyUsageOID.SERVER_AUTH]
    )
    assert key.key_size == 3072
    assert not (tmp_path / "brisa-ca.key").exists()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "brisa-server.crt", tmp_path / "brisa-server.key")


def test_mobile_certificate_rejects_public_address_and_accidental_overwrite(tmp_path):
    with pytest.raises(ValueError):
        generate("8.8.8.8", tmp_path, False)
    generate("192.168.1.5", tmp_path, False)
    with pytest.raises(FileExistsError):
        generate("192.168.1.5", tmp_path, False)
