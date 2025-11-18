import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import sys

from cogs.shutdown import is_admin_or_owner


def is_owner():
    """Проверка на владельца для слэш-команд"""
    async def predicate(interaction: discord.Interaction) -> bool:
        return await interaction.client.is_owner(interaction.user)
    return app_commands.check(predicate)


class ConfirmView(discord.ui.View):
    def __init__(self, action_type: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.action_type = action_type
        self.value = None
        self.interaction = None

    @discord.ui.button(label='✅ Подтвердить', style=discord.ButtonStyle.danger, emoji='✅')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label='❌ Отменить', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.interaction = interaction
        self.stop()

    async def on_timeout(self):
        # Очищаем кнопки при таймауте
        if self.interaction:
            try:
                embed = discord.Embed(
                    title="⏰ Время вышло",
                    description="Подтверждение отменено по таймауту",
                    color=discord.Color.orange()
                )
                await self.interaction.edit_original_response(embed=embed, view=None)
            except:
                pass


class ShutdownConfirm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shutdown_confirm", description="Выключить бота с подтверждением (только для владельца)")
    @is_admin_or_owner()
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

        # Ждем ответа
        await view.wait()

        if view.value is True:
            # Подтверждение получено - выключение
            embed = discord.Embed(
                title="🔴 Выключение...",
                description="Бот выключается...",
                color=discord.Color.red()
            )
            await view.interaction.edit_original_response(embed=embed, view=None)

            print(f"🛑 Бот выключен пользователем {interaction.user} (ID: {interaction.user.id})")
            await asyncio.sleep(2)
            await self.bot.close()

        elif view.value is False:
            # Отмена
            embed = discord.Embed(
                title="✅ Действие отменено",
                description="Выключение отменено",
                color=discord.Color.green()
            )
            await view.interaction.edit_original_response(embed=embed, view=None)

    @app_commands.command(name="restart_confirm", description="Перезагрузить бота с подтверждением (только для владельца)")
    @is_admin_or_owner()
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

        # Ждем ответа
        await view.wait()

        if view.value is True:
            # Подтверждение получено - перезагрузка
            embed = discord.Embed(
                title="🔄 Перезагрузка...",
                description="Бот перезагружается...",
                color=discord.Color.orange()
            )
            await view.interaction.edit_original_response(embed=embed, view=None)

            print(f"🔄 Бот перезагружен пользователем {interaction.user} (ID: {interaction.user.id})")
            await asyncio.sleep(2)
            os.execv(sys.executable, ['python'] + sys.argv)

        elif view.value is False:
            # Отмена
            embed = discord.Embed(
                title="✅ Действие отменено",
                description="Перезагрузка отменена",
                color=discord.Color.green()
            )
            await view.interaction.edit_original_response(embed=embed, view=None)

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
    await bot.add_cog(ShutdownConfirm(bot))