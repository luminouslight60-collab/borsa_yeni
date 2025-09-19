# Canlı Borsa Dashboard

Bu proje, **Streamlit** ile geliştirilmiş interaktif bir borsa takip dashboardudur.  

## Özellikler
- Canlı borsa verisi (Yahoo Finance)
- Hareketli Ortalamalar (MA10, MA20, MA50)
- RSI ve MACD göstergeleri
- Alarm sistemi:
  - Fiyat üst/alt uyarısı
  - RSI aşırı alım/satım uyarısı
  - MACD kesişim uyarısı
- Alarm geçmişi CSV ve Excel olarak indirilebilir
- Tüm grafikler interaktiftir (Plotly)
- Gerçek zamanlı sesli veya sistem bildirimi

## Kurulum
1. Python 3.10+ yüklü olmalı
2. Gerekli paketleri kur:
```bash
pip install -r requirements.txt
