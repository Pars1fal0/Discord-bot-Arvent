import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import sys
import psutil


def is_admin_or_owner():
    """Проверка на владельца или администратора для слэш-команд"""

    async def predicate(interaction: discord.Interaction) -> bool:
        # Проверка владельца бота
        if await interaction.client.is_owner(interaction.user):
            return True
        # Проверка прав администратора на сервере
        if interaction.guild and interaction.user.guild_permissions.administrator:
            return True
        return False

    return app_commands.check(predicate)


def is_bot_owner():
    """Проверка на создателя бота для слэш-команд"""

    async def predicate(interaction: discord.Interaction) -> bool:
        return await interaction.client.is_owner(interaction.user)

    return app_commands.check(predicate)


class Shutdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Команды выключения и перезагрузки - только для создателя бота
    @app_commands.command(name="shutdown", description="Выключить бота (только для создателя)")
    @is_bot_owner()
    async def shutdown(self, interaction: discord.Interaction):
        """Выключить бота (только для создателя)"""
        embed = discord.Embed(
            title="🔴 Выключение...",
            description="Бот выключается...",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

        print(f"🛑 Бот выключен создателем {interaction.user} (ID: {interaction.user.id})")
        await asyncio.sleep(2)
        await self.bot.close()

    @app_commands.command(name="restart", description="Перезагрузить бота (только для создателя)")
    @is_bot_owner()
    async def restart(self, interaction: discord.Interaction):
        """Перезагрузить бота (только для создателя)"""
        embed = discord.Embed(
            title="🔄 Перезагрузка...",
            description="Бот перезагружается...",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

        print(f"🔄 Бот перезагружен создателем {interaction.user} (ID: {interaction.user.id})")
        await asyncio.sleep(2)
        os.execv(sys.executable, ['python'] + sys.argv)

    # Команда статуса остается для администраторов
    @app_commands.command(name="status", description="Показать статус бота (только для администраторов)")
    @is_admin_or_owner()
    async def status(self, interaction: discord.Interaction):
        """Показать статус бота (только для администраторов)"""
        try:
            # Статистика бота
            guilds_count = len(self.bot.guilds)
            users_count = len(self.bot.users)

            # Пинг
            latency = round(self.bot.latency * 1000)

            # Время работы
            if hasattr(self.bot, 'start_time'):
                uptime = discord.utils.utcnow() - self.bot.start_time
                uptime_str = str(uptime).split('.')[0]
            else:
                uptime_str = "Неизвестно"

            # Использование памяти
            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # в MB

            embed = discord.Embed(
                title="🤖 Статус бота",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            embed.add_field(name="🖥️ Серверов", value=guilds_count, inline=True)
            embed.add_field(name="👥 Пользователей", value=users_count, inline=True)
            embed.add_field(name="📡 Пинг", value=f"{latency}ms", inline=True)

            embed.add_field(name="⏰ Время работы", value=uptime_str, inline=True)
            embed.add_field(name="💾 Память", value=f"{memory_usage:.2f} MB", inline=True)
            embed.add_field(name="📚 Коги", value=len(self.bot.cogs), inline=True)

            # Статус команд
            total_commands = len([cmd for cmd in self.bot.tree.walk_commands()])
            embed.add_field(name="⚙️ Слэш-команды", value=total_commands, inline=True)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    # Обработчик ошибок для команд создателя
    @shutdown.error
    @restart.error
    async def owner_command_error(self, interaction: discord.Interaction, error):
        """Обработчик ошибок для команд создателя"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="❌ Доступ запрещен",
                description="Эта команда только для создателя бота!",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Произошла ошибка",
                description=f"```{str(error)}```",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Shutdown(bot))