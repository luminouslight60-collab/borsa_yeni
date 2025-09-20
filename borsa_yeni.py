import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
import streamlit as st
from io import BytesIO
import platform
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ----------------------
# Bildirim ve ses
# ----------------------
try:
    if platform.system() == "Windows":
        import winsound
    else:
        import subprocess
except:
    st.warning("Bildirim modülü yüklenemedi.")

# ----------------------
# Yardımcı Fonksiyonlar
# ----------------------
@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    df = df.dropna()
    if df.empty:
        st.warning(f"{ticker} için veri alınamadı.")
    return df

def compute_ma(df, windows):
    for w in windows:
        df[f"MA{w}"] = df["Close"].rolling(w).mean()
    return df

def compute_rsi(df, period=14):
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    delta = close.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(gain, index=close.index).rolling(period).mean()
    roll_down = pd.Series(loss, index=close.index).rolling(period).mean()
    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_macd(df, short=12, long=26, signal=9):
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    exp1 = close.ewm(span=short, adjust=False).mean()
    exp2 = close.ewm(span=long, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - signal_line
    return pd.DataFrame({"MACD": macd, "Signal": signal_line, "Hist": hist}, index=df.index)

def save_alert(symbol, message):
    log_file = "alerts_log.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([[now, symbol, message]], columns=["Tarih", "Sembol", "Mesaj"])
    if os.path.exists(log_file):
        old = pd.read_csv(log_file)
        updated = pd.concat([old, new_entry], ignore_index=True)
    else:
        updated = new_entry
    updated.to_csv(log_file, index=False)
    try:
        if platform.system() == "Windows":
            winsound.Beep(1000, 500)
        else:
            subprocess.run(['say', message])
    except:
        pass

def load_alerts():
    log_file = "alerts_log.csv"
    if os.path.exists(log_file):
        return pd.read_csv(log_file)
    return pd.DataFrame(columns=["Tarih", "Sembol", "Mesaj"])

def clear_alerts(mode="all", n=None):
    log_file = "alerts_log.csv"
    if not os.path.exists(log_file):
        return
    df = pd.read_csv(log_file)

    if mode == "all":
        df = pd.DataFrame(columns=df.columns)  # tümünü temizle
    elif mode == "first_n" and n is not None:
        df = df.iloc[n:] if len(df) > n else pd.DataFrame(columns=df.columns)  # ilk n kaydı sil

    df.to_csv(log_file, index=False)

def check_alerts(symbol, df, rsi, macd_df, alerts):
    messages = []
    last_close = float(df["Close"].iloc[-1])

    price_above = alerts.get("price_above")
    if price_above and last_close > float(price_above):
        msg = f"🚀 {symbol}: Fiyat {price_above} üzerine çıktı! (Şu an: {last_close:.2f})"
        messages.append(msg)
        save_alert(symbol, msg)

    price_below = alerts.get("price_below")
    if price_below and last_close < float(price_below):
        msg = f"📉 {symbol}: Fiyat {price_below} altına indi! (Şu an: {last_close:.2f})"
        messages.append(msg)
        save_alert(symbol, msg)

    if rsi is not None and alerts.get("rsi_alert"):
        last_rsi = float(rsi.iloc[-1])
        if last_rsi > 70:
            msg = f"🔥 {symbol}: RSI {last_rsi:.1f} → Aşırı Alım!"
            messages.append(msg); save_alert(symbol, msg)
        elif last_rsi < 30:
            msg = f"❄️ {symbol}: RSI {last_rsi:.1f} → Aşırı Satım!"
            messages.append(msg); save_alert(symbol, msg)

    if macd_df is not None and len(macd_df) > 2 and alerts.get("macd_alert"):
        macd_prev, macd_last = float(macd_df["MACD"].iloc[-2]), float(macd_df["MACD"].iloc[-1])
        signal_prev, signal_last = float(macd_df["Signal"].iloc[-2]), float(macd_df["Signal"].iloc[-1])
        if macd_prev < signal_prev and macd_last > signal_last:
            msg = f"✅ {symbol}: MACD yukarı kesişim (Al sinyali)!"
            messages.append(msg); save_alert(symbol, msg)
        elif macd_prev > signal_prev and macd_last < signal_last:
            msg = f"⚠️ {symbol}: MACD aşağı kesişim (Sat sinyali)!"
            messages.append(msg); save_alert(symbol, msg)

    return messages

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Alarmlar')
    return output.getvalue()

# ----------------------
# Streamlit Arayüzü
# ----------------------
st.set_page_config(page_title="Canlı Borsa Dashboard", layout="wide")
st.title("📈 Canlı Borsa Dashboard")

# ----------------------
# Sidebar Ayarlar
# ----------------------
with st.sidebar:
    st.header("⚙️ Ayarlar")
    symbols_text = st.text_input("Hisseler (virgülle ayır):", "ASELS.IS, THYAO.IS")
    period = st.selectbox("Dönem", ["1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","max"], index=2)
    interval = st.selectbox("Zaman Aralığı", ["1m","5m","15m","30m","60m","1d","1wk"], index=4)
    refresh_seconds = st.number_input("Yenileme (saniye)", min_value=15, max_value=600, value=60, step=15)
    st.divider()
    st.subheader("📊 İndikatörler")
    ma10 = st.checkbox("MA10", value=True)
    ma20 = st.checkbox("MA20", value=True)
    ma50 = st.checkbox("MA50", value=False)
    show_rsi = st.checkbox("RSI (14)", value=True)
    show_macd = st.checkbox("MACD (12,26,9)", value=True)
    st.divider()
    st.subheader("🚨 Alarm Ayarları")
    price_above = st.number_input("Fiyat üstüne çıkarsa uyar:", min_value=0.0, step=0.1, value=0.0)
    price_below = st.number_input("Fiyat altına inerse uyar:", min_value=0.0, step=0.1, value=0.0)
    rsi_alert = st.checkbox("RSI uyarılarını aç", value=True)
    macd_alert = st.checkbox("MACD uyarılarını aç", value=True)

symbols = [s.strip() for s in symbols_text.split(",") if s.strip()]
alerts_config = {
    "price_above": price_above if price_above > 0 else None,
    "price_below": price_below if price_below > 0 else None,
    "rsi_alert": rsi_alert,
    "macd_alert": macd_alert
}

# ----------------------
# Otomatik Yenileme
# ----------------------
st_autorefresh(interval=refresh_seconds * 1000, key="datarefresh")

# ----------------------
# Grafikleri ve Alarmları Göster
# ----------------------
tabs = st.tabs(symbols)
def plot_symbol(tab, symbol):
    with tab:
        df = fetch_data(symbol, period, interval)
        if df.empty: return
        ma_windows = [w for w, enabled in zip([10,20,50],[ma10,ma20,ma50]) if enabled]
        if ma_windows: df = compute_ma(df, ma_windows)
        rsi = compute_rsi(df) if show_rsi else None
        macd_df = compute_macd(df) if show_macd else None

        # Fiyat grafiği
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Fiyat"))
        for w in ma_windows:
            fig.add_trace(go.Scatter(x=df.index, y=df[f"MA{w}"], mode="lines", name=f"MA{w}"))
        fig.update_layout(title=f"{symbol} Fiyat Grafiği", xaxis_rangeslider_visible=False, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        # RSI grafiği
        if show_rsi and rsi is not None:
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=rsi.index, y=rsi, mode="lines", name="RSI"))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
            fig_rsi.update_layout(title="RSI (14)", template="plotly_dark")
            st.plotly_chart(fig_rsi, use_container_width=True)

        # MACD grafiği
        if show_macd and macd_df is not None:
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(x=macd_df.index, y=macd_df["MACD"], mode="lines", name="MACD"))
            fig_macd.add_trace(go.Scatter(x=macd_df.index, y=macd_df["Signal"], mode="lines", name="Signal"))
            fig_macd.add_trace(go.Bar(x=macd_df.index, y=macd_df["Hist"], name="Hist"))
            fig_macd.update_layout(title="MACD (12,26,9)", template="plotly_dark")
            st.plotly_chart(fig_macd, use_container_width=True)

        # Son fiyatlar
        st.subheader("📋 Son 20 Kayıt")
        st.dataframe(df.tail(20))

        # Alarmlar
        alerts = check_alerts(symbol, df, rsi, macd_df, alerts_config)
        if alerts: st.error(" | ".join(alerts))

for i, sym in enumerate(symbols): plot_symbol(tabs[i], sym)

# ----------------------
# Alarm Geçmişi ve Temizleme
# ----------------------
st.divider()
st.subheader("📜 Alarm Geçmişi")
alerts_df = load_alerts()

# Temizleme
clear_option = st.selectbox("🧹 Alarm Geçmişini Temizle:", 
                            ["İlk 25", "İlk 50", "İlk 75", "Tümünü Temizle"])

if st.button("Temizle"):
    if clear_option == "İlk 25":
        clear_alerts(mode="first_n", n=25)
    elif clear_option == "İlk 50":
        clear_alerts(mode="first_n", n=50)
    elif clear_option == "İlk 75":
        clear_alerts(mode="first_n", n=75)
    else:
        clear_alerts(mode="all")
        
    st.success("Alarm geçmişi güncellendi!")
    st.experimental_rerun()


# Tablo ve Excel indirme
alerts_df = load_alerts()
if not alerts_df.empty:
    st.dataframe(alerts_df)
    excel_data = to_excel(alerts_df)
    st.download_button(label="📥 Alarm Geçmişini Excel Olarak İndir",
                       data=excel_data,
                       file_name="alarm_gecmisi.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Henüz kaydedilmiş alarm yok.")

# Son güncelleme
st.caption(f"⏳ Son güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

