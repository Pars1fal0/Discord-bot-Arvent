import discord
from discord.ext import commands
import os
from dotenv import load_dotenv  # <— добавили

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.presences = True
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents, help_command=None)

    async def setup_hook(self):
        # Автозагрузка когов из ./cogs (если папка есть)
        if os.path.isdir('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        print(f'✅ Загружен ког: {filename[:-3]}')
                    except Exception as e:
                        print(f'❌ Ошибка загрузки {filename}: {e}')

    async def on_ready(self):
        print(f'🤖 Бот {self.user} запущен!')
        print(f'📊 Подключен к {len(self.guilds)} серверам')
        await self.change_presence(activity=discord.Game(name="!help"))

bot = MyBot()

if __name__ == "__main__":
    load_dotenv()  # <— читаем .env
    token = os.getenv("DISCORD_TOKEN")

    if not token or not isinstance(token, str) or token.strip() == "":
        raise RuntimeError(
            "DISCORD_TOKEN не найден. Укажи токен в .env или переменной окружения."
        )

    bot.run(token)
