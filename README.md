# DUELUM test boti

Telegram bot: 1–11 sinf, fanlar bo'yicha 20 ta tasodifiy savolli test, reyting, 3 til (uz/ru/en), majburiy obuna (@DUELUM), admin tugmasi.

## Sozlash
1. @BotFather'dan token oling (`/newbot`).
2. **Botni @DUELUM kanaliga ADMIN qiling** (aks holda obunani tekshira olmaydi va hech kim botdan foydalana olmaydi).
3. Muhit o'zgaruvchilari: `BOT_TOKEN` (majburiy), `CHANNEL` (`@DUELUM`), `ADMIN_USERNAME` (`barhayot_madaminov`).

## Lokal ishga tushirish
```
pip install -r requirements.txt
cp .env.example .env   # tokenni yozing
export $(cat .env | xargs) && python main.py
```

## GitHub + Render
1. `git init && git add . && git commit -m "bot" && git branch -M main`
2. GitHub'da yangi repo oching, `git remote add origin <repo-url> && git push -u origin main`
3. render.com → New → Web Service → repo'ni tanlang. Build: `pip install -r requirements.txt`, Start: `python main.py`
4. Environment bo'limida `BOT_TOKEN` ni kiriting. Deploy.
5. Bepul Render xizmati 15 daqiqa so'rovsiz qolsa uxlab qoladi. Uxlamasligi uchun uptimerobot.com'da Render URL'ni (`/health`) har 5 daqiqada ping qiling.
6. Bepul Render'da fayl tizimi doimiy emas: qayta deploydan keyin `bot.db` (reyting) o'chadi. Doimiy saqlash uchun Render'da pullik disk yoki Postgres kerak.

## Savollar
Fayl nomi: `questions/{sinf}_{fan}.json`, masalan `5_history.json`. Fan kalitlari: math, mother, english, nature (1–4-sinf), history, geo, bio, physics, chem, info.
Format: `questions/_namuna.json`. Har faylda 100 ta savol bo'lishi kerak; bot ulardan 20 tasini tasodifiy tanlaydi.
Matematika (1–11) `python gen_math.py` bilan avtomatik yaratiladi.
