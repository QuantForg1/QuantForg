"""MT5 Gateway request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    """Broker credentials — accepted only by the Windows gateway.

    Never persist these in Railway environment variables.
    """

    login: int = Field(..., gt=0)
    password: str = Field(..., min_length=1)
    server: str = Field(..., min_length=1, max_length=128)
    path: str = Field(default="", max_length=512)


class AttachRequest(BaseModel):
    """Reuse an already logged-in MT5 terminal session (no broker password).

    Suitable when the Windows terminal is already authenticated (e.g. XM demo).
    Broker secrets still never leave the Windows host / terminal.
    """

    path: str = Field(
        default="",
        max_length=512,
        description="Optional path to terminal64.exe; otherwise MT5_TERMINAL_PATH",
    )


class TradeRequestBody(BaseModel):
    """Normalized trade payload for check / margin / profit / send."""

    symbol: str = Field(..., min_length=1, max_length=32)
    action: str = Field(
        default="buy",
        description=(
            "buy | sell | buy_limit | sell_limit | buy_stop | sell_stop | sltp"
        ),
    )
    volume: float = Field(default=0.01, ge=0)
    price: float = Field(default=0, ge=0)
    sl: float = Field(default=0, ge=0)
    tp: float = Field(default=0, ge=0)
    stop_loss: float | None = Field(default=None, ge=0)
    take_profit: float | None = Field(default=None, ge=0)
    deviation: int = Field(default=20, ge=0, le=1000)
    slippage: int | None = Field(default=None, ge=0, le=1000)
    magic: int = Field(default=0, ge=0)
    comment: str = Field(default="quantforg", max_length=31)
    close_price: float | None = Field(default=None, ge=0)
    position: int = Field(default=0, ge=0, description="Position ticket for close/SLTP")
    order_ticket: int = Field(default=0, ge=0, description="Pending order ticket")
    oms_kind: str = Field(
        default="",
        max_length=32,
        description="deal | pending | sltp | modify_pending | close",
    )

    def as_runtime_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "volume": self.volume,
            "price": self.price,
            "sl": self.sl if self.stop_loss is None else self.stop_loss,
            "tp": self.tp if self.take_profit is None else self.take_profit,
            "deviation": self.deviation if self.slippage is None else self.slippage,
            "magic": self.magic,
            "comment": self.comment,
            "close_price": self.close_price,
            "position": self.position,
            "order_ticket": self.order_ticket,
            "oms_kind": self.oms_kind,
        }


class CancelRequest(BaseModel):
    ticket: int = Field(..., gt=0)
