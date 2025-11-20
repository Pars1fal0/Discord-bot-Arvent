import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


def get_owner_id():
    """Получить OWNER_ID из .env файла"""
    owner_id = os.getenv('OWNER_ID')
    if owner_id:
        try:
            return int(owner_id)
        except (ValueError, TypeError):
            print("❌ Ошибка: OWNER_ID в .env файле должен быть числом")
            return None
    else:
        print("❌ Ошибка: OWNER_ID не найден в .env файле")
        return None


def is_bot_owner():
    """Проверка на создателя бота для слэш-команд"""

    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = get_owner_id()
        if owner_id is None:
            # Если OWNER_ID не установлен, используем стандартную проверку
            return await interaction.client.is_owner(interaction.user)

        is_owner = interaction.user.id == owner_id
        print(
            f"🔍 Проверка прав: пользователь {interaction.user} (ID: {interaction.user.id}) - создатель: {is_owner} (ожидаемый ID: {owner_id})")
        return is_owner

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
        self.owner_id = get_owner_id()

    @app_commands.command(name="whoami", description="Показать информацию о правах пользователя")
    async def whoami(self, interaction: discord.Interaction):
        """Показать информацию о правах пользователя"""
        owner_id = get_owner_id()
        is_bot_owner = owner_id and interaction.user.id == owner_id
        is_admin = interaction.guild and interaction.user.guild_permissions.administrator

        embed = discord.Embed(
            title="👤 Информация о правах",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="Пользователь", value=f"{interaction.user.mention} (ID: {interaction.user.id})",
                        inline=False)
        embed.add_field(name="Создатель бота", value="✅ Да" if is_bot_owner else "❌ Нет", inline=True)
        embed.add_field(name="Администратор сервера", value="✅ Да" if is_admin else "❌ Нет", inline=True)

        if owner_id:
            embed.add_field(name="Ожидаемый ID создателя", value=owner_id, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="shutdown_confirm", description="Выключить бота с подтверждением (только для создателя)")
    @is_bot_owner()
    async def shutdown_confirm(self, interaction: discord.Interaction):
        """Выключить бота с подтверждением (только для создателя)"""
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

            print(f"🛑 Бот выключен создателем {interaction.user} (ID: {interaction.user.id})")
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

    @app_commands.command(name="restart_confirm",
                          description="Перезагрузить бота с подтверждением (только для создателя)")
    @is_bot_owner()
    async def restart_confirm(self, interaction: discord.Interaction):
        """Перезагрузить бота с подтверждением (только для создателя)"""
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

            print(f"🔄 Бот перезагружен создателем {interaction.user} (ID: {interaction.user.id})")
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

    # Обработчик ошибок для команд создателя
    @shutdown_confirm.error
    @restart_confirm.error
    async def owner_command_error(self, interaction: discord.Interaction, error):
        """Обработчик ошибок для команд создателя"""
        if isinstance(error, app_commands.CheckFailure):
            owner_id = get_owner_id()
            is_owner = owner_id and interaction.user.id == owner_id

            print(f"🚫 Отказ в доступе: {interaction.user} (ID: {interaction.user.id}) - создатель: {is_owner}")

            embed = discord.Embed(
                title="❌ Доступ запрещен",
                description="Эта команда только для создателя бота!",
                color=discord.Color.red()
            )
            embed.add_field(name="Ваш ID", value=interaction.user.id, inline=True)
            embed.add_field(name="Вы создатель?", value="✅ Да" if is_owner else "❌ Нет", inline=True)

            if owner_id:
                embed.add_field(name="Ожидаемый ID создателя", value=owner_id, inline=False)

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