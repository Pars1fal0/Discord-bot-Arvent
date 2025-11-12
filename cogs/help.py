import discord
from discord.ext import commands


class HelpInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx):
        em = discord.Embed(
            title="**📘 Команды для пользователей**",
            description="Доступные команды, которые не требуют прав администратора.",
            color=discord.Color.blurple()
        )

        general_commands = [
            "`!help` — показать этот список",
            "`!sinfo` — информация о сервере",
            "`!uinfo` — информация о себе"
        ]

        em.add_field(
            name="Основные команды:",
            value="\n".join(general_commands),
            inline=False
        )

        is_admin = False
        if ctx.guild and isinstance(ctx.author, discord.Member):
            is_admin = ctx.author.guild_permissions.administrator

        if not is_admin:
            stream_commands = [
                "`!stream` — список стрим-команд",
                "`!stream linktwitch <логин>` — привязать Twitch",
                "`!stream linkyoutube <channel_id>` — привязать YouTube",
                "`!stream show [участник]` — посмотреть привязанные аккаунты",
                "`!stream unlink <twitch|youtube>` — отвязать платформу"
            ]

            em.add_field(
                name="Стрим-инструменты:",
                value="\n".join(stream_commands),
                inline=False
            )

        await ctx.send(embed=em)


async def setup(bot):
    await bot.add_cog(HelpInfo(bot))