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


class Shutdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shutdown", description="Выключить бота (только для администраторов)")
    @is_admin_or_owner()
    async def shutdown(self, interaction: discord.Interaction):
        """Выключить бота (только для администраторов)"""
        try:
            embed = discord.Embed(
                title="🔴 Выключение бота",
                description="Бот выключается...",
                color=discord.Color.red()
            )
            embed.add_field(name="Инициатор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Время", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)

            await interaction.response.send_message(embed=embed)

            # Даем время на отправку сообщения
            await asyncio.sleep(1)

            print(f"🛑 Бот выключен пользователем {interaction.user} (ID: {interaction.user.id})")
            await self.bot.close()

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка при выключении",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="restart", description="Перезагрузить бота (только для администраторов)")
    @is_admin_or_owner()
    async def restart(self, interaction: discord.Interaction):
        """Перезагрузить бота (только для администраторов)"""
        try:
            embed = discord.Embed(
                title="🔄 Перезагрузка бота",
                description="Бот перезагружается...",
                color=discord.Color.orange()
            )
            embed.add_field(name="Инициатор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Время", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)

            await interaction.response.send_message(embed=embed)

            # Даем время на отправку сообщения
            await asyncio.sleep(1)

            print(f"🔄 Бот перезагружен пользователем {interaction.user} (ID: {interaction.user.id})")

            # Перезапуск бота
            os.execv(sys.executable, ['python'] + sys.argv)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка при перезагрузке",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="reload", description="Перезагрузить ког или все коги (только для администраторов)")
    @app_commands.describe(cog="Название кога для перезагрузки (оставьте пустым для перезагрузки всех)")
    @is_admin_or_owner()
    async def reload(self, interaction: discord.Interaction, cog: str = None):
        """Перезагрузить ког или все коги (только для администраторов)"""
        try:
            if cog:
                # Перезагрузка конкретного кога
                try:
                    await self.bot.reload_extension(f"cogs.{cog}")
                    embed = discord.Embed(
                        title="✅ Ког перезагружен",
                        description=f"Ког `{cog}` успешно перезагружен!",
                        color=discord.Color.green()
                    )
                    print(f"🔄 Ког {cog} перезагружен пользователем {interaction.user}")
                except commands.ExtensionNotLoaded:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description=f"Ког `{cog}` не загружен!",
                        color=discord.Color.red()
                    )
                except commands.ExtensionNotFound:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description=f"Ког `{cog}` не найден!",
                        color=discord.Color.red()
                    )
                except Exception as e:
                    embed = discord.Embed(
                        title="❌ Ошибка перезагрузки",
                        description=f"Ошибка при перезагрузке кога `{cog}`: {str(e)}",
                        color=discord.Color.red()
                    )
            else:
                # Перезагрузка всех когов
                success = []
                failed = []

                for filename in os.listdir('./cogs'):
                    if filename.endswith('.py'):
                        cog_name = filename[:-3]
                        try:
                            await self.bot.reload_extension(f'cogs.{cog_name}')
                            success.append(cog_name)
                        except Exception as e:
                            failed.append(f"{cog_name}: {str(e)}")

                embed = discord.Embed(
                    title="🔄 Перезагрузка всех когов",
                    color=discord.Color.blue()
                )

                if success:
                    embed.add_field(
                        name="✅ Успешно перезагружены",
                        value="\n".join([f"`{cog}`" for cog in success]),
                        inline=False
                    )

                if failed:
                    embed.add_field(
                        name="❌ Ошибки перезагрузки",
                        value="\n".join([f"`{error}`" for error in failed]),
                        inline=False
                    )

                print(f"🔄 Все коги перезагружены пользователем {interaction.user}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка при перезагрузке",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="load", description="Загрузить ког (только для администраторов)")
    @app_commands.describe(cog="Название кога для загрузки")
    @is_admin_or_owner()
    async def load(self, interaction: discord.Interaction, cog: str):
        """Загрузить ког (только для администраторов)"""
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            embed = discord.Embed(
                title="✅ Ког загружен",
                description=f"Ког `{cog}` успешно загружен!",
                color=discord.Color.green()
            )
            print(f"📥 Ког {cog} загружен пользователем {interaction.user}")
            await interaction.response.send_message(embed=embed)

        except commands.ExtensionAlreadyLoaded:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Ког `{cog}` уже загружен!",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except commands.ExtensionNotFound:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Ког `{cog}` не найден!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка загрузки",
                description=f"Ошибка при загрузке кога `{cog}`: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unload", description="Выгрузить ког (только для администраторов)")
    @app_commands.describe(cog="Название кога для выгрузки")
    @is_admin_or_owner()
    async def unload(self, interaction: discord.Interaction, cog: str):
        """Выгрузить ког (только для администраторов)"""
        try:
            if cog == "shutdown":
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Нельзя выгрузить ког shutdown!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await self.bot.unload_extension(f"cogs.{cog}")
            embed = discord.Embed(
                title="✅ Ког выгружен",
                description=f"Ког `{cog}` успешно выгружен!",
                color=discord.Color.orange()
            )
            print(f"📤 Ког {cog} выгружен пользователем {interaction.user}")
            await interaction.response.send_message(embed=embed)

        except commands.ExtensionNotLoaded:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Ког `{cog}` не загружен!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка выгрузки",
                description=f"Ошибка при выгрузке кога `{cog}`: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cogs_list", description="Показать список всех когов (только для администраторов)")
    @is_admin_or_owner()
    async def cogs_list(self, interaction: discord.Interaction):
        """Показать список всех когов (только для администраторов)"""
        try:
            loaded_cogs = []
            unloaded_cogs = []

            # Получаем все файлы когов
            cogs_dir = './cogs'
            if os.path.exists(cogs_dir):
                for filename in os.listdir(cogs_dir):
                    if filename.endswith('.py'):
                        cog_name = filename[:-3]
                        if f"cogs.{cog_name}" in self.bot.extensions:
                            loaded_cogs.append(cog_name)
                        else:
                            unloaded_cogs.append(cog_name)

            embed = discord.Embed(
                title="📚 Список когов",
                color=discord.Color.blue()
            )

            if loaded_cogs:
                embed.add_field(
                    name="🟢 Загруженные коги",
                    value="\n".join([f"`{cog}`" for cog in sorted(loaded_cogs)]),
                    inline=True
                )

            if unloaded_cogs:
                embed.add_field(
                    name="🔴 Незагруженные коги",
                    value="\n".join([f"`{cog}`" for cog in sorted(unloaded_cogs)]),
                    inline=True
                )

            if not loaded_cogs and not unloaded_cogs:
                embed.description = "Коги не найдены"

            embed.add_field(
                name="📋 Команды управления",
                value=(
                    "`/load <ког>` - загрузить ког\n"
                    "`/unload <ког>` - выгрузить ког\n"
                    "`/reload <ког>` - перезагрузить ког\n"
                    "`/reload` - перезагрузить все коги\n"
                    "`/restart` - перезапустить бота\n"
                    "`/shutdown` - выключить бота"
                ),
                inline=False
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="bot_status", description="Показать статус бота (только для администраторов)")
    @is_admin_or_owner()
    async def bot_status(self, interaction: discord.Interaction):
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

    @commands.Cog.listener()
    async def on_ready(self):
        """Устанавливает время старта бота"""
        if not hasattr(self.bot, 'start_time'):
            self.bot.start_time = discord.utils.utcnow()
            print(f"🤖 Бот запущен в {self.bot.start_time}")

    # Обработчик ошибок для слэш-команд
    @shutdown.error
    @restart.error
    @reload.error
    @load.error
    @unload.error
    @cogs_list.error
    @bot_status.error
    async def slash_command_error(self, interaction: discord.Interaction, error):
        """Обработчик ошибок для слэш-команд"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="❌ Доступ запрещен",
                description="Эта команда доступна только администраторам сервера или владельцу бота!",
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