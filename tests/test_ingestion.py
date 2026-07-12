"""Tests for BAREKAT platform."""

import pytest
from barekat.ingestion.hl7_parser import HL7Parser


def test_hl7_parser_valid_message():
    parser = HL7Parser()
    message = "MSH|^~\\&|SENDING|FACILITY|RECEIVING|FACILITY|20240101120000||ADT^A01|MSG001|P|2.5\nPID|1||PT00001^^^FACILITY||DOE^JOHN"
    assert parser.validate(message) is True
    parsed = parser.parse(message)
    assert parsed.message_type != ""


def test_hl7_parser_invalid_message():
    parser = HL7Parser()
    assert parser.validate("") is False
    assert parser.validate("INVALID") is False
