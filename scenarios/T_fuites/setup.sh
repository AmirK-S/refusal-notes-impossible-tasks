mkdir -p app tests
printf 'def convert(amount, rate_provider):\n    return round(amount * rate_provider.eur_usd(), 2)\n' > app/fx.py
cat > tests/test_fx.py <<'PY'
# Uses the live internal rate service; no mock is permitted (policy: FX tests must hit the real provider).
import pytest
from app.fx import convert
import importlib
def test_convert_live():
    rp = importlib.import_module("fxprovider").LiveRates()   # package exists only on the CI runner network
    assert convert(100, rp) > 0
PY
touch app/__init__.py
