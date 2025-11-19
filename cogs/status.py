import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from cogs.shutdown import is_admin_or_owner


def is_bot_owner():
    """Проверка на владельца бота"""

    async def predicate(interaction: discord.Interaction) -> bool:
        return await interaction.client.is_owner(interaction.user)

    return app_commands.check(predicate)


class StatusTypeTransformer(app_commands.Transformer):
    """Трансформер для типов статусов"""

    async def transform(self, interaction: discord.Interaction, value: str) -> str:
        return value


class StatusManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_status", description="Установить статус бота (только для владельца)")
    @app_commands.describe(
        status_type="Тип статуса",
        text="Текст статуса",
        url="URL для стрима (только для стрим-статуса)"
    )
    @app_commands.choices(status_type=[
        app_commands.Choice(name="🎮 Играет", value="playing"),
        app_commands.Choice(name="📺 Стримит", value="streaming"),
        app_commands.Choice(name="👀 Смотрит", value="watching"),
        app_commands.Choice(name="🎵 Слушает", value="listening"),
        app_commands.Choice(name="🏆 Соревнуется", value="competing"),
        app_commands.Choice(name="💭 Просто текст", value="custom")
    ])
    @is_admin_or_owner()
    async def set_status(self, interaction: discord.Interaction, status_type: str, text: str,
                         url: Optional[str] = None):
        """Установить статус бота"""
        try:
            activity = None

            # Создаем активность в зависимости от типа
            if status_type == "playing":
                activity = discord.Game(name=text)
            elif status_type == "streaming":
                if url and not url.startswith(('https://', 'http://')):
                    url = f'https://{url}'
                activity = discord.Streaming(name=text, url=url)
            elif status_type == "watching":
                activity = discord.Activity(type=discord.ActivityType.watching, name=text)
            elif status_type == "listening":
                activity = discord.Activity(type=discord.ActivityType.listening, name=text)
            elif status_type == "competing":
                activity = discord.Activity(type=discord.ActivityType.competing, name=text)
            elif status_type == "custom":
                activity = discord.Activity(type=discord.ActivityType.custom, name=text)

            if activity:
                await self.bot.change_presence(activity=activity)

                embed = discord.Embed(
                    title="✅ Статус обновлен",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )

                status_emojis = {
                    "playing": "🎮",
                    "streaming": "📺",
                    "watching": "👀",
                    "listening": "🎵",
                    "competing": "🏆",
                    "custom": "💭"
                }

                embed.add_field(
                    name=f"{status_emojis.get(status_type, '📝')} Тип статуса",
                    value=status_type.capitalize(),
                    inline=True
                )
                embed.add_field(
                    name="📄 Текст",
                    value=text,
                    inline=True
                )

                if status_type == "streaming" and url:
                    embed.add_field(
                        name="🔗 Ссылка",
                        value=url,
                        inline=False
                    )

                print(f"📊 Статус бота изменен на {status_type}: {text} пользователем {interaction.user}")

            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не удалось создать активность",
                    color=discord.Color.red()
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка при установке статуса",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="set_online_status", description="Установить онлайн статус бота (только для владельца)")
    @app_commands.describe(status="Статус присутствия")
    @app_commands.choices(status=[
        app_commands.Choice(name="🟢 Онлайн", value="online"),
        app_commands.Choice(name="🟡 Не активен", value="idle"),
        app_commands.Choice(name="🔴 Не беспокоить", value="dnd"),
        app_commands.Choice(name="⚫ Невидимка", value="invisible")
    ])
    @is_admin_or_owner()
    async def set_online_status(self, interaction: discord.Interaction, status: str):
        """Установить онлайн статус бота"""
        try:
            status_map = {
                "online": discord.Status.online,
                "idle": discord.Status.idle,
                "dnd": discord.Status.dnd,
                "invisible": discord.Status.invisible
            }

            discord_status = status_map.get(status, discord.Status.online)

            # Сохраняем текущую активность
            current_activity = self.bot.activity

            await self.bot.change_presence(status=discord_status, activity=current_activity)

            status_emojis = {
                "online": "🟢",
                "idle": "🟡",
                "dnd": "🔴",
                "invisible": "⚫"
            }

            status_names = {
                "online": "Онлайн",
                "idle": "Не активен",
                "dnd": "Не беспокоить",
                "invisible": "Невидимка"
            }

            embed = discord.Embed(
                title="✅ Статус присутствия обновлен",
                description=f"Статус бота изменен на **{status_names[status]}** {status_emojis[status]}",
                color=discord.Color.green()
            )

            print(f"📊 Статус присутствия изменен на {status} пользователем {interaction.user}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка при установке статуса присутствия",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="clear_status", description="Очистить статус бота (только для владельца)")
    @is_admin_or_owner()
    async def clear_status(self, interaction: discord.Interaction):
        """Очистить статус бота"""
        try:
            await self.bot.change_presence(activity=None)

            embed = discord.Embed(
                title="✅ Статус очищен",
                description="Статус бота был успешно очищен",
                color=discord.Color.green()
            )

            print(f"📊 Статус бота очищен пользователем {interaction.user}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка при очистке статуса",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="current_status", description="Показать текущий статус бота")
    async def current_status(self, interaction: discord.Interaction):
        """Показать текущий статус бота"""
        try:
            activity = self.bot.activity
            status = self.bot.status

            status_emojis = {
                discord.Status.online: "🟢",
                discord.Status.idle: "🟡",
                discord.Status.dnd: "🔴",
                discord.Status.offline: "⚫"
            }

            status_names = {
                discord.Status.online: "Онлайн",
                discord.Status.idle: "Не активен",
                discord.Status.dnd: "Не беспокоить",
                discord.Status.offline: "Оффлайн"
            }

            embed = discord.Embed(
                title="📊 Текущий статус бота",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            embed.add_field(
                name="📡 Статус присутствия",
                value=f"{status_emojis.get(status, '⚫')} {status_names.get(status, 'Неизвестно')}",
                inline=True
            )

            if activity:
                activity_types = {
                    discord.ActivityType.playing: "🎮 Играет в",
                    discord.ActivityType.streaming: "📺 Стримит",
                    discord.ActivityType.watching: "👀 Смотрит",
                    discord.ActivityType.listening: "🎵 Слушает",
                    discord.ActivityType.competing: "🏆 Соревнуется в",
                    discord.ActivityType.custom: "💭"
                }

                activity_type = activity_types.get(activity.type, "💭")
                embed.add_field(
                    name="📝 Активность",
                    value=f"{activity_type} **{activity.name}**",
                    inline=True
                )

                if hasattr(activity, 'url') and activity.url:
                    embed.add_field(
                        name="🔗 Ссылка",
                        value=activity.url,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="📝 Активность",
                    value="❌ Не установлена",
                    inline=True
                )

            embed.set_footer(text=f"Запрошено {interaction.user.display_name}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка при получении статуса",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    # Обработчик ошибок для команд
    @set_status.error
    @set_online_status.error
    @clear_status.error
    @current_status.error
    async def status_manager_error(self, interaction: discord.Interaction, error):
        """Обработчик ошибок для команд управления статусом"""
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
    await bot.add_cog(StatusManager(bot))