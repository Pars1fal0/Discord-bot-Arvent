import discord
from discord.ext import commands
import json
import os
import random

AUTO_ROLE_ID = 1411068140024107031
WELCOME_CONFIG_FILE = "welcome_channels.json"


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channels: dict[int, int] = self.load_config()

    # ===== Работа с конфигом =====
    def load_config(self) -> dict[int, int]:
        if not os.path.exists(WELCOME_CONFIG_FILE):
            return {}
        try:
            with open(WELCOME_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {int(k): int(v) for k, v in data.items()}
        except Exception as e:
            print(f"[AutoRole] Не удалось загрузить {WELCOME_CONFIG_FILE}: {e}")
            return {}

    def save_config(self):
        try:
            with open(WELCOME_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.welcome_channels, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AutoRole] Не удалось сохранить {WELCOME_CONFIG_FILE}: {e}")

    # ===== Выдача роли + приветствие =====
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        role = guild.get_role(AUTO_ROLE_ID)

        # 1) Авто-роль
        if role is None:
            print(f"[AutoRole] Не нашёл роль с ID {AUTO_ROLE_ID} на сервере {guild.name}")
        else:
            try:
                await member.add_roles(role, reason="Авто-выдача роли новому участнику")
                print(f"[AutoRole] Выдал роль {role.name} пользователю {member} на сервере {guild.name}")
            except discord.Forbidden:
                print("[AutoRole] Нет прав на выдачу роли (проверь права бота и позицию роли).")
            except discord.HTTPException as e:
                print(f"[AutoRole] Ошибка Discord API при выдаче роли: {e}")

        # 2) Канал приветствий
        channel_id = self.welcome_channels.get(guild.id)
        channel = guild.get_channel(channel_id) if channel_id is not None else None

        if channel is None:
            return  # не настроен канал — просто выходим

        # 3) Рандомное приветствие
        greetings = [
            "Добро пожаловать",
            "Приветствуем",
            "Рады видеть",
            "Привет",
            "Васап",
            "Салют",
        ]

        emojis = ["🎉", "👋", "🌟", "😊", "🦄", "🚀", "🎊", "🤗"]

        embed = discord.Embed(
            title=f"{random.choice(greetings)}, {member.display_name}! {random.choice(emojis)}",
            description=f"Рады тебя видеть на сервере **{member.guild.name}**!\n",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(content=member.mention, embed=embed)
        except discord.Forbidden:
            print(f"[AutoRole] Нет прав писать в канал {channel} на сервере {guild.name}")
        except discord.HTTPException as e:
            print(f"[AutoRole] Ошибка при отправке приветствия: {e}")

    # ===== Команда для установки канала приветствий =====
    @commands.command(name="setwelcome")
    @commands.has_permissions(manage_guild=True)
    async def set_welcome_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Установить канал для приветственных сообщений"""
        self.welcome_channels[ctx.guild.id] = channel.id
        self.save_config()
        await ctx.send(f"✅ Канал приветствий установлен: {channel.mention}")

    @set_welcome_channel.error
    async def set_welcome_channel_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ У тебя нет прав `Управление сервером`.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Укажи текстовый канал, например: `!setwelcome #welcome`")
        else:
            print(f"[AutoRole] Ошибка в команде setwelcome: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRole(bot))
