# การวิเคราะห์คริปโต Bitkub (รายงานภาษาไทย)

`scripts/bitkub_crypto_analyzer.py` เป็นตัววิเคราะห์คริปโตแบบ standalone ที่ทำงาน
คู่กับระบบหลัก (ไม่แตะ pipeline หุ้น) — ให้รายงานตัดสินใจภาษาไทยสำหรับคู่เหรียญบน
Bitkub เช่น `THB_BTC`, `THB_ETH`, `THB_KUB`

## วิธีที่ข้อมูลคริปโตเข้าสู่ระบบ

| ข้อมูล | แหล่งที่มา | เหตุผล |
| --- | --- | --- |
| ราคา THB ล่าสุด / 24ชม. / วอลุ่มบาท | Bitkub public ticker (`/api/market/ticker`, ไม่ต้อง auth) | ราคาตลาดไทยจริง |
| กราฟแท่งเทียน OHLCV (USD) | Binance klines, fallback: Coingecko market_chart (รวม hourly → daily candles เอง) | Bitkub ไม่มี REST kline endpoint; ตลาด global มีสภาพคล่องลึกกว่า |
| อัตราแปลง THB | implied rate = ราคา Bitkub ÷ ราคา global | แปลงจุดเข้า/SL/เป้าหมายเป็นบาท |

หมายเหตุ: REST API ของ Bitkub (v1–v4) ไม่มี endpoint แท่งเทียนสาธารณะ — ตัวเว็บ
ใช้ TradingView chart API ภายในที่ไม่เสถียรสำหรับ automation จึงเลือกข้อมูล
global เป็นฐานวิเคราะห์ และใช้ Bitkub เฉพาะราคาท้องถิ่น

## ตัวชี้วัดที่คำนวณ

MA5/10/20/50, RSI(14), MACD(12,26,9), Bollinger(20,2), ATR(14), วอลุ่มเทียบค่าเฉลี่ย
10 แท่ง — รวมเป็นคะแนน 0-100 และสัญญาณภาษาไทย

## การใช้งาน

```bash
# รายงานเต็ม (LLM ภาษาไทย + Telegram)
python scripts/bitkub_crypto_analyzer.py --symbols THB_BTC,THB_ETH

# เฉพาะเทคนิค (ไม่ใช้ LLM / ไม่ส่ง Telegram)
python scripts/bitkub_crypto_analyzer.py --no-llm --no-telegram

# JSON สำหรับ pipeline อื่น
python scripts/bitkub_crypto_analyzer.py --json
```

## การตั้งค่า (.env)

| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
| --- | --- | --- |
| `BITKUB_SYMBOLS` | `THB_BTC,THB_ETH,THB_KUB` | คู่เหรียญที่จะวิเคราะห์ |
| `BITKUB_LLM_BASE_URL` | `http://llm-server:11434/v1` | OpenAI-compatible LLM (Ollama/xKiro) |
| `BITKUB_LLM_MODEL` | `typhoon-thai:latest` | โมเดลที่เขียนรายงานไทย |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | — | ใช้ร่วมกับระบบแจ้งเตือนหลัก |

เหรียญที่ไม่มีบน Binance (เช่น KUB) ใช้ Coingecko id ผ่าน `COINGECKO_IDS` ในสคริปต์
หรือเพิ่ม override ใน `SYMBOL_MAP_OVERRIDES`

## การรันอัตโนมัติ

`.github/workflows/bitkub-crypto.yml` — cron ทุกวัน 08:00 น. เวลาไทย (คริปโตซื้อขาย
24/7 จึงรันทุกวัน ไม่เว้นเสาร์-อาทิตย์) + manual dispatch ตั้ง Secrets:
`BITKUB_LLM_BASE_URL`, `BITKUB_LLM_MODEL`, `LLM_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID` (คู่เหรียญใช้ Variables `BITKUB_SYMBOLS` ได้)

## ขอบเขต

- วิเคราะห์เทคนิค + ข่าว/พื้นฐานเฉพาะเหรียญยังไม่รวม (ต่างจาก pipeline หุ้น)
- คริปโตเสี่ยงสูงและซื้อขาย 24/7 — รายงานเป็นการอ้างอิง ไม่ใช่คำแนะนำการลงทุน
