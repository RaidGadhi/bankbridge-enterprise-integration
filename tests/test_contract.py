from pathlib import Path
import re
import yaml


def test_api_contract_money_pattern():
    path = Path(__file__).resolve().parents[1] / 'deploy/apiconnect/bankbridge-openapi.yaml'
    spec = yaml.safe_load(path.read_text())
    pattern = spec['components']['schemas']['Payment']['properties']['amount']['pattern']
    assert re.fullmatch(pattern, '500.00')
    assert not re.fullmatch(pattern, '1.001')
