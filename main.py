import discord
from discord.ext import commands
import os
import asyncio


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Автоматическая загрузка всех когов из папки cogs
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


# Создание и запуск бота
bot = MyBot()

# Запуск бота
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)