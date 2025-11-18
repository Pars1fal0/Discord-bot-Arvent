# sinfo.py
import discord
from discord import app_commands
from discord.ext import commands


class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sinfo", description="Показать информацию о сервере")
    async def sinfo(self, interaction: discord.Interaction):
        guild = interaction.guild

        em = discord.Embed(
            title="**🖥️ Информация о дискорд сервере**",
            color=discord.Color.blurple()
        )

        if guild.icon:
            em.set_thumbnail(url=guild.icon.url)

        # Основная информация о сервере
        em.add_field(name="Название сервера:", value=f'{guild.name}', inline=True)

        owner_value = guild.owner.mention if guild.owner else f'{guild.owner}'
        em.add_field(name="Владелец:", value=owner_value, inline=True)
        em.add_field(name="Пользователи:", value=f'{guild.member_count}', inline=True)

        # Подробная статистика
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        total_channels = text_channels + voice_channels

        em.add_field(name="Текстовые каналы:", value=f'{text_channels}', inline=True)
        em.add_field(name="Голосовые каналы:", value=f'{voice_channels}', inline=True)
        em.add_field(name="Всего каналов:", value=f'{total_channels}', inline=True)

        em.add_field(name="Роли:", value=f'{len(guild.roles)}', inline=True)
        em.add_field(name="Бусты:", value=f'{guild.premium_subscription_count}', inline=True)
        em.add_field(name="Уровень буста:", value=f'{guild.premium_tier}', inline=True)

        # Время создания с красивым форматированием
        created_at = guild.created_at
        em.add_field(
            name="Дата создания:",
            value=f'<t:{int(created_at.timestamp())}:D>\n(<t:{int(created_at.timestamp())}:R>)',
            inline=False
        )

        # Уровень проверки
        verification_levels = {
            discord.VerificationLevel.none: "Нет",
            discord.VerificationLevel.low: "Низкий",
            discord.VerificationLevel.medium: "Средний",
            discord.VerificationLevel.high: "Высокий",
            discord.VerificationLevel.highest: "Самый высокий"
        }
        em.add_field(
            name="Уровень проверки:",
            value=verification_levels.get(guild.verification_level, "Неизвестно"),
            inline=True
        )

        await interaction.response.send_message(embed=em)


async def setup(bot):
    await bot.add_cog(ServerInfo(bot))