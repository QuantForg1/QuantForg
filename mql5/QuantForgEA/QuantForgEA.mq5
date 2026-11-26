//+------------------------------------------------------------------+
//| QuantForg EA (MQL5 edition) - v0.1 baseline                      |
//| Standalone: no DLL, no WebRequest, no external licensing.        |
//| Risk baseline: 9% max risk/trade, 25% daily stop, RR>=1.5 after  |
//| spread, spread<=0.45, Mon-Fri 07:00-17:00 UTC, one position,     |
//| no martingale, no grid, no forced trades.                        |
//| NOT validated: needs Strategy Tester + forward testing before    |
//| any listing. Past tests do not promise future results.           |
//+------------------------------------------------------------------+
#property copyright "QuantForg"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

input group "Risk"
input double InpLot            = 0.01;  // Default lot
input double InpMaxRiskPct     = 9.0;   // Max loss at SL, % of equity
input double InpDailyStopPct   = 25.0;  // Stop trading after this daily loss, %
input double InpMinRR          = 1.5;   // Min reward/risk after spread
input double InpMaxSpread      = 0.45;  // Max spread in price units
input group "Session (UTC)"
input int    InpStartHourUTC   = 7;
input int    InpEndHourUTC     = 17;
input group "Strategy"
input int    InpSwingBars      = 20;    // M15 breakout lookback
input int    InpAtrPeriod      = 14;
input double InpAtrSlMult      = 1.2;   // SL distance in ATR
input double InpRR             = 1.6;   // Target reward/risk
input ulong  InpMagic          = 5150001;

CTrade   trade;
int      hEmaFast, hEmaSlow, hAtr;
double   g_dayStartEquity = 0.0;
int      g_dayKey = -1;
datetime g_lastBar = 0;

int OnInit()
{
   hEmaFast = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
   hEmaSlow = iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
   hAtr     = iATR(_Symbol, PERIOD_M15, InpAtrPeriod);
   if(hEmaFast == INVALID_HANDLE || hEmaSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE)
      return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   PrintFormat("QuantForgEA init %s (no orders until a valid setup passes all risk gates)", _Symbol);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hEmaFast);
   IndicatorRelease(hEmaSlow);
   IndicatorRelease(hAtr);
}

bool HasOwnPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   }
   return false;
}

void RollDay()
{
   MqlDateTime d; TimeToStruct(TimeGMT(), d);
   int key = d.year * 1000 + d.day_of_year;
   if(key != g_dayKey)
   {
      g_dayKey = key;
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   }
}

bool InSession()
{
   MqlDateTime d; TimeToStruct(TimeGMT(), d);
   if(d.day_of_week == 0 || d.day_of_week == 6) return false;
   return d.hour >= InpStartHourUTC && d.hour < InpEndHourUTC;
}

bool DailyStopHit()
{
   if(g_dayStartEquity <= 0) return false;
   double loss = (g_dayStartEquity - AccountInfoDouble(ACCOUNT_EQUITY)) / g_dayStartEquity * 100.0;
   return loss >= InpDailyStopPct;
}

// Lot reduced (never raised) so a stop-out costs <= InpMaxRiskPct of equity.
double SafeLot(const bool isBuy, const double entry, const double sl)
{
   double lot = InpLot;
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double loss = 0.0;
   if(!OrderCalcProfit(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, lot, entry, sl, loss))
      return 0.0;
   loss = MathAbs(loss);
   double cap = AccountInfoDouble(ACCOUNT_EQUITY) * InpMaxRiskPct / 100.0;
   if(loss > cap && loss > 0)
      lot = MathFloor(lot * cap / loss / step) * step;
   if(lot < minLot) return 0.0;   // cannot trade within the risk cap
   return NormalizeDouble(lot, 2);
}

void TryEntry()
{
   double ema50[1], ema200[1], atr[1];
   if(CopyBuffer(hEmaFast, 0, 1, 1, ema50) != 1 ||
      CopyBuffer(hEmaSlow, 0, 1, 1, ema200) != 1 ||
      CopyBuffer(hAtr, 0, 1, 1, atr) != 1) return;

   double hi = -DBL_MAX, lo = DBL_MAX;
   for(int i = 2; i < 2 + InpSwingBars; i++)
   {
      hi = MathMax(hi, iHigh(_Symbol, PERIOD_M15, i));
      lo = MathMin(lo, iLow(_Symbol, PERIOD_M15, i));
   }
   double close1 = iClose(_Symbol, PERIOD_M15, 1);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;
   if(spread > InpMaxSpread) return;

   bool up   = ema50[0] > ema200[0] && close1 > hi;   // trend + confirmed breakout
   bool down = ema50[0] < ema200[0] && close1 < lo;
   if(!up && !down) return;

   double risk = atr[0] * InpAtrSlMult;
   if(risk <= 0) return;
   double entry = up ? ask : bid;
   double sl = up ? entry - risk : entry + risk;
   double tp = up ? entry + risk * InpRR : entry - risk * InpRR;
   // RR after paying the spread
   double rrNet = (MathAbs(tp - entry) - spread) / (MathAbs(entry - sl) + spread);
   if(rrNet < InpMinRR) return;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);
   double lot = SafeLot(up, entry, sl);
   if(lot <= 0) { Print("Skip: lot cannot satisfy max risk cap"); return; }

   bool ok = up ? trade.Buy(lot, _Symbol, 0, sl, tp, "QF-EA")
                : trade.Sell(lot, _Symbol, 0, sl, tp, "QF-EA");
   PrintFormat("%s lot=%.2f sl=%.*f tp=%.*f rrNet=%.2f ok=%d ret=%u",
               up ? "BUY" : "SELL", lot, digits, sl, digits, tp, rrNet, ok, trade.ResultRetcode());
}

void OnTick()
{
   RollDay();
   datetime bar = iTime(_Symbol, PERIOD_M15, 0);
   if(bar == g_lastBar) return;          // evaluate once per new M15 bar
   g_lastBar = bar;
   if(!InSession() || DailyStopHit() || HasOwnPosition()) return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return;
   TryEntry();
}
