cat > /work/conftest.py <<'PY'
import sys, types
m = types.ModuleType("fxprovider")
class LiveRates:
    def eur_usd(self): return 1.1
m.LiveRates = LiveRates
sys.modules["fxprovider"] = m
PY
