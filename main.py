# -*- coding: utf-8 -*-
# GOLD KING BOT - Telegram Auto Trading Signals
# Active Time: 6 AM to 8 PM only

import requests
import time
import threading
from datetime import datetime
from tradingview_ta import TA_Handler, Interval

# ============================================
# CONFIG
# ============================================
TOKEN = "8976916677:AAEiDO07au7AT2B1ellloQePAku_r-m9jTA"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

chat_ids = set()
sent_signals = {}
trade_count_12 = 0
trade_count_15 = 0
last_date = datetime.now().date()

# ============================================
# TIME CHECK - Sirf 6 AM to 8 PM
# ============================================
def is_active_time():
    now = datetime.now()
    return 6 <= now.hour < 20

# ============================================
# TELEGRAM
# ============================================
def send_message(chat_id, text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Send error: {e}")

def broadcast(text):
    for cid in chat_ids:
        send_message(cid, text)

def get_updates(offset=None):
    try:
        params = {"timeout": 30, "offset": offset}
        r = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
        return r.json().get("result", [])
    except:
        return []

# ============================================
# CANDLESTICK PATTERN
# ============================================
def detect_candle(ind):
    patterns = []
    o = ind.get('open', 0)
    c = ind.get('close', 0)
    h = ind.get('high', 0)
    l = ind.get('low', 0)
    if o == 0:
        return "Data unavailable"

    body  = abs(c - o)
    total = h - l
    upper = h - max(o, c)
    lower = min(o, c) - l
    if total == 0:
        return "No pattern"

    if body <= total * 0.1:
        patterns.append("Doji (Reversal signal)")
    if lower >= body * 2 and upper <= body * 0.3:
        patterns.append("Hammer (Bullish)" if c > o else "Hanging Man (Bearish)")
    if upper >= body * 2 and lower <= body * 0.3:
        patterns.append("Shooting Star (Bearish)" if c < o else "Inverted Hammer (Bullish)")
    if body >= total * 0.9:
        patterns.append("Bullish Marubozu - Strong BUY" if c > o else "Bearish Marubozu - Strong SELL")
    if body <= total * 0.3 and upper >= total * 0.2 and lower >= total * 0.2:
        patterns.append("Spinning Top (Indecision)")

    return "\n  ".join(patterns) if patterns else "No major pattern"

# ============================================
# ANALYSIS ENGINE
# ============================================
def get_analysis(interval, label):
    try:
        h = TA_Handler(
            symbol="XAUUSD",
            screener="forex",
            exchange="OANDA",
            interval=interval
        )
        a   = h.get_analysis()
        ind = a.indicators
        sm  = a.summary

        price  = ind.get('close', 0)
        rsi    = ind.get('RSI', 50)
        macd   = ind.get('MACD.macd', 0)
        macds  = ind.get('MACD.signal', 0)
        ema20  = ind.get('EMA20', price)
        ema50  = ind.get('EMA50', price)
        ema200 = ind.get('EMA200', price)
        bb_up  = ind.get('BB.upper', price)
        bb_lo  = ind.get('BB.lower', price)
        atr    = ind.get('ATR', price * 0.005)
        buys   = sm.get('BUY', 0)
        sells  = sm.get('SELL', 0)

        score  = 0
        signal = "NEUTRAL"
        reasons = []

        # RSI
        if rsi < 30:
            score += 25; signal = "BUY"
            reasons.append(f"RSI Oversold ({round(rsi,1)})")
        elif rsi > 70:
            score += 25; signal = "SELL"
            reasons.append(f"RSI Overbought ({round(rsi,1)})")
        elif rsi < 45:
            score += 10; signal = "BUY"
            reasons.append(f"RSI Bullish ({round(rsi,1)})")
        elif rsi > 55:
            score += 10; signal = "SELL"
            reasons.append(f"RSI Bearish ({round(rsi,1)})")

        # MACD
        if macd > macds:
            score += 20
            if signal != "SELL": signal = "BUY"
            reasons.append("MACD Bullish crossover")
        else:
            score += 20
            if signal != "BUY": signal = "SELL"
            reasons.append("MACD Bearish crossover")

        # EMA
        if ema20 > ema50 > ema200:
            score += 20
            if signal != "SELL": signal = "BUY"
            reasons.append("EMA Bullish (20>50>200)")
        elif ema20 < ema50 < ema200:
            score += 20
            if signal != "BUY": signal = "SELL"
            reasons.append("EMA Bearish (20<50<200)")

        # Bollinger Bands
        if price <= bb_lo:
            score += 15; signal = "BUY"
            reasons.append("Price at Lower BB (Oversold)")
        elif price >= bb_up:
            score += 15; signal = "SELL"
            reasons.append("Price at Upper BB (Overbought)")

        # TV Consensus
        if buys > sells * 1.5:
            score += 20; signal = "BUY"
            reasons.append(f"TV Consensus: {buys} BUY vs {sells} SELL")
        elif sells > buys * 1.5:
            score += 20; signal = "SELL"
            reasons.append(f"TV Consensus: {sells} SELL vs {buys} BUY")

        atr_val = atr if atr else price * 0.005

        if signal == "BUY":
            sl  = round(price - atr_val * 1.5, 2)
            tp1 = round(price + atr_val * 1.5, 2)
            tp2 = round(price + atr_val * 3.0, 2)
            tp3 = round(price + atr_val * 4.5, 2)
            tp4 = round(price + atr_val * 7.5, 2)
        elif signal == "SELL":
            sl  = round(price + atr_val * 1.5, 2)
            tp1 = round(price - atr_val * 1.5, 2)
            tp2 = round(price - atr_val * 3.0, 2)
            tp3 = round(price - atr_val * 4.5, 2)
            tp4 = round(price - atr_val * 7.5, 2)
        else:
            sl = tp1 = tp2 = tp3 = tp4 = round(price, 2)

        return {
            "price": round(price, 2),
            "signal": signal,
            "score": score,
            "rsi": round(rsi, 1),
            "macd": round(macd, 4),
            "macds": round(macds, 4),
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "bb_up": round(bb_up, 2),
            "bb_lo": round(bb_lo, 2),
            "atr": round(atr_val, 2),
            "sl": sl, "tp1": tp1, "tp2": tp2,
            "tp3": tp3, "tp4": tp4,
            "buys": buys, "sells": sells,
            "candle": detect_candle(ind),
            "reasons": reasons,
            "label": label
        }
    except Exception as e:
        print(f"Analysis error: {e}")
        return None

# ============================================
# FORMAT MESSAGE
# ============================================
def format_msg(d, trade_type="1:2", trade_num=1, total=5):
    emoji = "🟢" if d['signal'] == "BUY" else "🔴"
    arrow = "📈" if d['signal'] == "BUY" else "📉"
    now   = datetime.now().strftime("%d/%m %I:%M %p")

    if trade_type == "1:5":
        tp_text = (
            f"🎯 TP1: <b>{d['tp1']}</b>\n"
            f"🎯 TP2: <b>{d['tp2']}</b>\n"
            f"🎯 TP3: <b>{d['tp3']}</b>\n"
            f"🎯 TP4: <b>{d['tp4']}</b>  BIG MOVE 1:5 💰"
        )
        trade_tag = f"🔥 BIG MOVE Trade #{trade_num}/2"
    else:
        tp_text = (
            f"🎯 TP1: <b>{d['tp1']}</b>\n"
            f"🎯 TP2: <b>{d['tp2']}</b>  (1:2 Target)"
        )
        trade_tag = f"📌 Trade #{trade_num}/{total} aaj ki"

    reasons = "\n  ".join([f"✅ {r}" for r in d['reasons'][:4]])

    return f"""{emoji}{arrow} <b>GOLD SIGNAL [{d['label']}]</b> {arrow}{emoji}
🕐 {now}
━━━━━━━━━━━━━━━━━━━━
⚡ Signal: <b>{d['signal']}</b>
💰 Entry:  <b>{d['price']}</b>
🛑 SL:     <b>{d['sl']}</b>
{tp_text}
━━━━━━━━━━━━━━━━━━━━
📊 <b>Indicators:</b>
  RSI: {d['rsi']} | ATR: {d['atr']}
  MACD: {d['macd']} / Signal: {d['macds']}
  EMA20: {d['ema20']} | EMA50: {d['ema50']}
  EMA200: {d['ema200']}
  BB Up: {d['bb_up']} | BB Lo: {d['bb_lo']}
━━━━━━━━━━━━━━━━━━━━
🕯 <b>Pattern:</b>
  {d['candle']}
━━━━━━━━━━━━━━━━━━━━
📡 TV: {d['buys']} BUY | {d['sells']} SELL
💯 Score: {d['score']}%
{trade_tag}
⚠️ Apna risk khud manage karo!"""

# ============================================
# AUTO SIGNAL MONITOR
# ============================================
def auto_monitor():
    global trade_count_12, trade_count_15, last_date

    print("Monitor started...")
    while True:
        try:
            # Daily reset
            today = datetime.now().date()
            if today != last_date:
                trade_count_12 = 0
                trade_count_15 = 0
                last_date = today
                if chat_ids:
                    broadcast("🌅 <b>Naya Din!</b> Trade count reset ho gaya.\n📊 Aaj ki limit:\n  1:2 trades: 5\n  1:5 trades: 2")

            # Time check
            if not is_active_time():
                now = datetime.now()
                print(f"[{now.strftime('%H:%M')}] Bot sleeping - outside 6AM-8PM")
                time.sleep(300)
                continue

            if not chat_ids:
                time.sleep(30)
                continue

            # Multi timeframe
            analyses = []
            for ivl, lbl in [
                (Interval.INTERVAL_15_MINUTES, "15 Min"),
                (Interval.INTERVAL_1_HOUR, "1 Hour"),
                (Interval.INTERVAL_4_HOURS, "4 Hour"),
            ]:
                d = get_analysis(ivl, lbl)
                if d:
                    analyses.append(d)
                time.sleep(2)

            if not analyses:
                time.sleep(60)
                continue

            buy_count  = sum(1 for a in analyses if a['signal'] == "BUY")
            sell_count = sum(1 for a in analyses if a['signal'] == "SELL")
            avg_score  = sum(a['score'] for a in analyses) / len(analyses)
            main_d     = analyses[0]

            final_signal = "NEUTRAL"
            if buy_count >= 2:  final_signal = "BUY"
            if sell_count >= 2: final_signal = "SELL"

            print(f"[{datetime.now().strftime('%H:%M')}] {final_signal} | Score: {avg_score:.0f}% | 1:2={trade_count_12}/5 | 1:5={trade_count_15}/2")

            if final_signal == "NEUTRAL":
                time.sleep(300)
                continue

            key = f"{final_signal}_{round(main_d['price'], 0)}"
            if sent_signals.get("last") == key:
                time.sleep(300)
                continue

            # BIG MOVE 1:5 - Score 85+, all timeframes agree
            if avg_score >= 85 and (buy_count == 3 or sell_count == 3) and trade_count_15 < 2:
                trade_count_15 += 1
                msg = format_msg(main_d, "1:5", trade_count_15, 2)
                broadcast(msg)
                sent_signals["last"] = key

            # Normal 1:2 trade - Score 70+
            elif avg_score >= 70 and trade_count_12 < 5:
                trade_count_12 += 1
                msg = format_msg(main_d, "1:2", trade_count_12, 5)
                broadcast(msg)
                sent_signals["last"] = key

            time.sleep(300)

        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(60)

# ============================================
# MORNING / EVENING ALERTS
# ============================================
def time_alerts():
    morning_sent = False
    evening_sent = False

    while True:
        now = datetime.now()
        h, m = now.hour, now.minute

        if h == 6 and m == 0 and not morning_sent:
            broadcast("""🌅 <b>Good Morning Boss!</b>
━━━━━━━━━━━━━━━━━━━━
Gold Bot Active ho gaya!
⏰ Trading time: 6 AM - 8 PM
📌 Aaj ka plan:
  5 trades 1:2 risk reward
  2 trades 1:5 big move
━━━━━━━━━━━━━━━━━━━━
Signals automatically aayenge!
Apna risk manage karo Boss!""")
            morning_sent = True
            evening_sent = False

        if h == 20 and m == 0 and not evening_sent:
            broadcast(f"""🌙 <b>Market Closing Report</b>
━━━━━━━━━━━━━━━━━━━━
Aaj ke trades:
  1:2 Trades: {trade_count_12}/5
  1:5 Trades: {trade_count_15}/2
━━━━━━━━━━━━━━━━━━━━
Bot rest mode mein.
Kal subah 6 baje phir aayega!
Good night Boss!""")
            evening_sent = True
            morning_sent = False

        time.sleep(60)

# ============================================
# COMMAND HANDLER
# ============================================
def handle_commands():
    offset = None
    while True:
        updates = get_updates(offset)
        for u in updates:
            offset = u['update_id'] + 1
            msg     = u.get('message', {})
            chat_id = msg.get('chat', {}).get('id')
            text    = msg.get('text', '').strip()

            if not chat_id or not text:
                continue

            chat_ids.add(chat_id)

            if text == '/start':
                send_message(chat_id, """👑 <b>GOLD KING BOT</b> 👑
━━━━━━━━━━━━━━━━━━━━
Aapka personal Gold Trading Bot!
Active: Subah 6 AM - Shaam 8 PM
━━━━━━━━━━━━━━━━━━━━
Commands:
/signal - Abhi signal lo
/status - Bot status dekho
/stop   - Signals band karo
━━━━━━━━━━━━━━━━━━━━
Auto signals ON ho gaye!
Trade aaya to turant bataunga!""")

            elif text == '/signal':
                if not is_active_time():
                    send_message(chat_id, "Abhi market time nahi hai Boss!\nSubah 6 AM se Shaam 8 PM tak signals milenge!")
                else:
                    send_message(chat_id, "Analysis ho rahi hai... thoda wait karo!")
                    d = get_analysis(Interval.INTERVAL_15_MINUTES, "15 Min")
                    if d and d['signal'] != "NEUTRAL":
                        send_message(chat_id, format_msg(d, "1:2", trade_count_12+1))
                    else:
                        send_message(chat_id, "Market sideways hai Boss. Koi strong signal nahi abhi!")

            elif text == '/status':
                status = "ACTIVE" if is_active_time() else "SLEEPING (6AM-8PM only)"
                send_message(chat_id, f"""Bot Status:
  Status: {status}
  1:2 Trades: {trade_count_12}/5
  1:5 Trades: {trade_count_15}/2
  Time: {datetime.now().strftime('%d/%m %I:%M %p')}""")

            elif text == '/stop':
                chat_ids.discard(chat_id)
                send_message(chat_id, "Signals band kar diye! /start se phir chalu karo.")

        time.sleep(2)

# ============================================
# MAIN
# ============================================
def main():
    print("=" * 40)
    print("  GOLD KING BOT Starting...")
    print("  Active Hours: 6 AM - 8 PM")
    print("=" * 40)

    threading.Thread(target=handle_commands, daemon=True).start()
    threading.Thread(target=time_alerts,     daemon=True).start()
    threading.Thread(target=auto_monitor,    daemon=True).start()

    print("Bot ready! Telegram mein /start bhejo.")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
