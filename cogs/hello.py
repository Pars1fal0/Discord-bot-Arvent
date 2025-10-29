import discord
from discord.ext import commands
import random

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        welcome_channel_id = None #Канал для приветствий, можно указать по айди или найти по имени

        if not welcome_channel_id:
            welcome_channel = discord.utils.get(member.guild.channels, name="welcome")

            if not welcome_channel:
                welcome_channel = discord.utils.get(member.guild.channels, name="приветствия")

            if not welcome_channel:
                welcome_channel = discord.utils.get(member.guild.text_channels, name="общий")

            if not welcome_channel:
                welcome_channel = discord.utils.get(member.guild.system_channel)

        else:
            welcome_channel = member.guild.get_channel(welcome_channel_id)

        if not welcome_channel:
            return

        greetings = [
            "Добро пожаловать"
            "Приветствуем"
            "Рады видеть"
            "Привет"
            "Васап"
            "Салют"
        ]

        emojis = ["🎉", "👋", "🌟", "😊", "🦄", "🚀", "🎊", "🤗"]

        embed = discord.Embed(
            title=f"{random.choice(greetings)}, {member.display_name}! {random.choice(emojis)}",
            description=f"Рады тебя видеть на сервере {member.guild.name}!",
            color=discord.Color.green()
        )

    @commands.command()
    async def set_welcome_channel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        embed = discord.Embed(
            title="Канал для приветствий установлен",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))


