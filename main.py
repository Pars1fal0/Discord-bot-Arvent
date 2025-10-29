import logging
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os

# Логи (по желанию)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Положите токен в .env как DISCORD_TOKEN=...")

# Интенты: для префикс-команд нужна message_content
intents = discord.Intents.default()
intents.message_content = True  # включите это же в портале Discord (Message Content Intent)

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    logging.info(f"✅ Вошёл как {bot.user} (id={bot.user.id})")
    # Синхронизация слэш-команд
    try:
        synced = await bot.tree.sync()
        logging.info(f"🔧 Синхронизировано слэш-команд: {len(synced)}")
    except Exception as e:
        logging.exception("Ошибка синхронизации слэш-команд: %s", e)

# Префикс-команда: !ping
@bot.command(name="ping", help="Показывает пинг бота")
async def ping(ctx: commands.Context):
    await ctx.reply(f"Pong! {round(bot.latency * 1000)} ms")

# Слэш-команда: /hello
@bot.tree.command(name="hello", description="Поздороваться")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Привет, {interaction.user.mention}! 👋")

if __name__ == "__main__":
    bot.run(TOKEN)
