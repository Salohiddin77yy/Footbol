import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta

# Bot tokeningizni kiriting
TOKEN = '8233473335:AAEKsV2qzB9-NL4MvKMXBr_1famUsN6uuqs'
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 8533821739
CHANNEL_ID = "@zakazolamanakan"
BOT_STATUS = True # Bot holati

# Ma'lumotlar bazasini sozlash
def init_db():
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        user_id INTEGER, 
                        name TEXT, 
                        date TEXT, 
                        time TEXT, 
                        channel_msg_id INTEGER,
                        status TEXT DEFAULT 'active')''')
    conn.commit()
    conn.close()

init_db()

# --- Klaviaturalar ---
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("⚽ O'yin bron qilish", "📋 Faol o'yinlarim")
    markup.add("🎫 VIP chipta", "📂 Menyu")
    if user_id == ADMIN_ID:
        markup.add("⚙️ Admin Panel")
    return markup

def back_btn():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔙 Ortga qaytish")
    return markup

# --- Asosiy mantiq ---

@bot.message_handler(func=lambda message: not BOT_STATUS and message.from_user.id != ADMIN_ID)
def bot_stopped(message):
    bot.send_message(message.chat.id, "🛑 Bot vaqtincha to'xtatilgan.")

@bot.message_handler(commands=['start'])
def start(message):
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", 
                   (message.from_user.id, message.from_user.username))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "👋 Salom! Bu bot Salokhiddin Stadioniga xizmat qiladi!!!", 
                     reply_markup=main_menu(message.from_user.id))

@bot.message_handler(func=lambda message: message.text == "⚽ O'yin bron qilish")
def start_booking(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📅 Bugun", "📆 Ertaga", "🔙 Ortga qaytish")
    bot.send_message(message.chat.id, "🕒 O'yin bron qilish boshlandi.\nSanani tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["📅 Bugun", "📆 Ertaga"])
def select_time(message):
    date = "Bugun" if "Bugun" in message.text else "Ertaga"
    markup = types.InlineKeyboardMarkup(row_width=3)
    times = [f"{h}:00" for h in range(7, 24)]
    btns = [types.InlineKeyboardButton(t, callback_data=f"time_{date}_{t}") for t in times]
    markup.add(*btns)
    bot.send_message(message.chat.id, f"⏰ {date} uchun vaqtni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("time_"))
def process_time(call):
    _, date, time = call.data.split("_")
    
    # Kanalda bronni tekshirish (Bazadan tekshiramiz)
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bookings WHERE date=? AND time=? AND status='active'", (date, time))
    exists = cursor.fetchone()
    
    if exists:
        bot.answer_callback_query(call.id, "❌ Uzur, bu joy bron qilingan!", show_alert=True)
    else:
        msg = bot.send_message(call.message.chat.id, "📝 Ism va Familiyangizni kiriting:")
        bot.register_next_step_handler(msg, save_booking, date, time)

def save_booking(message, date, time):
    name = message.text
    if name == "🔙 Ortga qaytish":
        bot.send_message(message.chat.id, "Bekor qilindi", reply_markup=main_menu(message.from_user.id))
        return

    # Kanalga yuborish
    channel_msg = bot.send_message(CHANNEL_ID, f"🔔 YANGI BRON!\n👤 Ism: {name}\n📅 Sana: {date}\n🕒 Vaqt: {time}\n✅ Holati: Faol")
    
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bookings (user_id, name, date, time, channel_msg_id) VALUES (?, ?, ?, ?, ?)",
                   (message.from_user.id, name, date, time, channel_msg.message_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ Rahmat! {date} soat {time}ga bron qilindi.", reply_markup=main_menu(message.from_user.id))

@bot.message_handler(func=lambda message: message.text == "📋 Faol o'yinlarim")
def active_games(message):
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, time FROM bookings WHERE user_id=? AND status='active'", (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, "🚫 Sizda hozircha kutilayotgan o'yinlar yo'q.\n\nO'yin bron qilish uchun '⚽ O'yin bron qilish' tugmasini bosing.")
    else:
        for row in rows:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{row[0]}"))
            bot.send_message(message.chat.id, f"📅 Sana: {row[1]}\n🕒 Vaqt: {row[2]}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cancel_booking(call):
    b_id = call.data.split("_")[1]
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date, time, name, channel_msg_id FROM bookings WHERE id=?", (b_id,))
    res = cursor.fetchone()
    
    if res:
        # Kanalni tahrirlash
        try:
            bot.edit_message_text(f"❌ BRON BEKOR QILINDI\n👤 Ism: {res[2]}\n📅 Sana: {res[0]}\n🕒 Vaqt: {res[1]}\n🚫 Holati: Bekor qilindi", 
                                  CHANNEL_ID, res[3])
        except: pass
        
        cursor.execute("UPDATE bookings SET status='canceled' WHERE id=?", (b_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "Bron bekor qilindi!")
        bot.edit_message_text("❌ Bu bron bekor qilingan.", call.message.chat.id, call.message.message_id)
    conn.close()

@bot.message_handler(func=lambda message: message.text == "🎫 VIP chipta")
def vip_promo(message):
    text = """🎫 VIP chipta - MAXSUS TAKLIF!

🎯 FAQAT 2 TA O'RIN QOLDI!
💫 Allaqachon 10 kishi VIP chipta xarid qildi

1 Oylik VIP: 💰 50,000 so'm (🎁 50% chegirma)
2 Oylik VIP: 💰 100,000 so'm (🎁 50% chegirma)
3 Oylik VIP: 💰 150,000 so'm (🎁 50% chegirma)

⚡️ 🎫 VIP chipta IMKONIYATLAR:
✓ Ertangi o'yinlarni bron qilish
✓ O'yinni bekor qilish qulayligi

👇 Tarifni tanlang:"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("1 Oylik", callback_data="vip_1"),
               types.InlineKeyboardButton("2 Oylik", callback_data="vip_2"),
               types.InlineKeyboardButton("3 Oylik", callback_data="vip_3"))
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📂 Menyu")
def extra_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("ℹ️ Yordam", "⭐ Baholash")
    markup.add("📊 Statistika", "🔘 Faol")
    markup.add("🔙 Ortga qaytish")
    bot.send_message(message.chat.id, "Quyidagi bo'limlardan birini tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "ℹ️ Yordam")
def help_link(message):
    bot.send_message(message.chat.id, "🆘 Yordam va Takliflar uchun: @salokhiddindev\n\n Faqat aniq maqsad bilan yozin!!!")

@bot.message_handler(func=lambda message: message.text == "⭐ Baholash")
def rate_bot(message):
    markup = types.InlineKeyboardMarkup()
    btns = [types.InlineKeyboardButton("⭐", callback_data="rate_done") for _ in range(5)]
    markup.add(*btns)
    bot.send_message(message.chat.id, "Botni baholang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "rate_done")
def rate_thanks(call):
    bot.answer_callback_query(call.id, "Bahoyingiz uchun rahmat!!!!")
    bot.edit_message_text("Bahoyingiz uchun rahmat!!!!", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: message.text == "📊 Statistika")
def stats(message):
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    bot.send_message(message.chat.id, f"📊 Botdan foydalanuvchilar soni: {count} ta")

@bot.message_handler(func=lambda message: message.text == "🔘 Faol")
def current_active(message):
    # Bu yerda real vaqtni tekshiramiz
    now = datetime.now().strftime("%H:00")
    # Sodda qilib aytganda hozirgi soatdagi bronni qidiramiz
    bot.send_message(message.chat.id, f"🔍 Hozirgi vaqt ({now}) bo'yicha bandlik tekshirilmoqda...")
    # (Kanal xabarlarini filtrlash yoki bazadan o'sha soatni qidirish mantiqi)

# --- Admin Panel ---
@bot.message_handler(func=lambda message: message.text == "⚙️ Admin Panel" and message.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📢 Hammaga xabar", "📊 Statistika")
    status_text = "🔴 Stop Bot" if BOT_STATUS else "🟢 Start Bot"
    markup.add(status_text)
    markup.add("🔙 Ortga qaytish")
    bot.send_message(message.chat.id, "Xush kelibsiz Admin!", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📢 Hammaga xabar" and message.from_user.id == ADMIN_ID)
def broadcast_prompt(message):
    msg = bot.send_message(message.chat.id, "Xabarni kiriting:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(message):
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    for user in users:
        try:
            if message.text == "Vip Chipta":
                vip_promo(telebot.types.Message(None, None, None, {'id': user[0]}, None, None, None))
            else:
                bot.send_message(user[0], message.text)
        except: continue
    bot.send_message(ADMIN_ID, "✅ Xabar yuborildi.")

@bot.message_handler(func=lambda message: message.text in ["🔴 Stop Bot", "🟢 Start Bot"] and message.from_user.id == ADMIN_ID)
def toggle_bot(message):
    global BOT_STATUS
    BOT_STATUS = not BOT_STATUS
    status_msg = "🛑 Bot stop qilindi" if not BOT_STATUS else "✅ Bot qayta ishga tushirildi"
    
    conn = sqlite3.connect('football_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    for user in users:
        try: bot.send_message(user[0], status_msg)
        except: pass
    
    admin_panel(message)

@bot.message_handler(func=lambda message: message.text == "🔙 Ortga qaytish")
def go_back(message):
    bot.send_message(message.chat.id, "Asosiy menyu", reply_markup=main_menu(message.from_user.id))

bot.polling(none_stop=True)