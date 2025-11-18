import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import sys


class ConfirmView(discord.ui.View):
    def __init__(self, action_type: str):
        super().__init__(timeout=60)
        self.action_type = action_type
        self.value = None

    @discord.ui.button(label='✅ Подтвердить', style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()

        if self.action_type == "shutdown":
            embed = discord.Embed(
                title="🔴 Выключение...",
                description="Бот выключается...",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            print(f"🛑 Бот выключен пользователем {interaction.user} (ID: {interaction.user.id})")
            await asyncio.sleep(2)
            await interaction.client.close()
        else:  # restart
            embed = discord.Embed(
                title="🔄 Перезагрузка...",
                description="Бот перезагружается...",
                color=discord.Color.orange()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            print(f"🔄 Бот перезагружен пользователем {interaction.user} (ID: {interaction.user.id})")
            await asyncio.sleep(2)
            os.execv(sys.executable, ['python'] + sys.argv)

    @discord.ui.button(label='❌ Отменить', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()

        embed = discord.Embed(
            title="✅ Действие отменено",
            description="Выключение/перезагрузка отменена",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ShutdownConfirm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shutdown_confirm", description="Выключить бота с подтверждением (только для владельца)")
    @app_commands.checks.is_owner()
    async def shutdown_confirm(self, interaction: discord.Interaction):
        """Выключить бота с подтверждением (только для владельца)"""
        embed = discord.Embed(
            title="🔴 Подтверждение выключения",
            description="Вы уверены, что хотите выключить бота?",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Для подтверждения",
            value="Нажмите кнопку ниже",
            inline=False
        )

        view = ConfirmView("shutdown")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="restart_confirm",
                          description="Перезагрузить бота с подтверждением (только для владельца)")
    @app_commands.checks.is_owner()
    async def restart_confirm(self, interaction: discord.Interaction):
        """Перезагрузить бота с подтверждением (только для владельца)"""
        embed = discord.Embed(
            title="🔄 Подтверждение перезагрузки",
            description="Вы уверены, что хотите перезагрузить бота?",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Для подтверждения",
            value="Нажмите кнопку ниже",
            inline=False
        )

        view = ConfirmView("restart")
        await interaction.response.send_message(embed=embed, view=view)

    # Обработчик ошибок для команд владельца
    @shutdown_confirm.error
    @restart_confirm.error
    async def owner_command_error(self, interaction: discord.Interaction, error):
        """Обработчик ошибок для команд владельца"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="❌ Доступ запрещен",
                description="Эта команда только для владельца бота!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ShutdownConfirm(bot))