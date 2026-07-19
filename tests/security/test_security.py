import pytest
from core.network_policy import validate_url
from core.security.request_controls import reject_executable_payload
from core.tool_registry import execute_tool
from core.auth import Principal, Role

def test_reject_code_payload():
    with pytest.raises(Exception): reject_executable_payload({"script":"import os\nos.system('id')"})

def test_private_url_blocked():
    with pytest.raises(ValueError): validate_url("http://127.0.0.1/")

def test_tool_registry_allows_calculator_not_python():
    p=Principal("u",{Role.ADMIN},{"*":{"*"}})
    assert execute_tool("calculator",{"expression":"2+2"},p)["result"]==4
    with pytest.raises(Exception): execute_tool("calculator",{"expression":"__import__('os')"},p)
