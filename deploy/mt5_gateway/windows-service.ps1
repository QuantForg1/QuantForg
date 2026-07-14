# QuantForg MT5 Gateway — Windows Service (NSSM example)
# Requires: NSSM (https://nssm.cc/) + Python 3.13 + MetaTrader5 package + terminal.

# 1. Install:
#    nssm install QuantForgMT5Gateway "C:\QuantForg\.venv\Scripts\python.exe" "-m" "services.mt5_gateway.main"
# 2. Set AppDirectory to repo root (C:\QuantForg)
# 3. Environment (NSSM → AppEnvironmentExtra):
#      MT5_GATEWAY_TOKEN=<strong-token>
#      MT5_GATEWAY_HOST=0.0.0.0
#      MT5_GATEWAY_PORT=8765
#      MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
#      MT5_GATEWAY_AUTO_ATTACH=true
# 4. Start:
#    nssm start QuantForgMT5Gateway
#
# NEVER put broker login/password in the service environment.
# Prefer MT5_GATEWAY_AUTO_ATTACH=true when the terminal stays logged in,
# or call POST /session/attach / POST /session/connect after the service is up.

Write-Host "See comments in this script for NSSM install steps."
