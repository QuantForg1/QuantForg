"""``python -m services.mt5_gateway`` entry — delegates to gated ``main.run``."""

from __future__ import annotations

from services.mt5_gateway.main import run

if __name__ == "__main__":
    run()
