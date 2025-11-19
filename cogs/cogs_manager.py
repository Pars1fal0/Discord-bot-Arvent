import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio

from cogs.shutdown import is_admin_or_owner


def is_bot_owner():
    """Проверка на владельца бота"""

    async def predicate(interaction: discord.Interaction) -> bool:
        return await interaction.client.is_owner(interaction.user)

    return app_commands.check(predicate)


class CogManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="load_cog", description="Загрузить новый ког (только для владельца)")
    @app_commands.describe(
        cog_name="Название файла кога (без .py)",
        code="Код Python для кога"
    )
    @is_admin_or_owner()
    async def load_cog(self, interaction: discord.Interaction, cog_name: str, code: str):
        """Загрузить новый ког из кода"""
        try:
            # Проверяем валидность имени кога
            if not cog_name.isidentifier():
                embed = discord.Embed(
                    title="❌ Неверное имя кога",
                    description="Имя кога должно быть валидным идентификатором Python (только буквы, цифры и подчеркивания, не начинаться с цифры)",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Создаем папку cogs если её нет
            os.makedirs('./cogs', exist_ok=True)

            file_path = f'./cogs/{cog_name}.py'

            # Проверяем, не существует ли уже ког с таким именем
            if os.path.exists(file_path):
                embed = discord.Embed(
                    title="❌ Ког уже существует",
                    description=f"Ког `{cog_name}` уже существует! Используйте `/reload_cog` для обновления.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Сохраняем код в файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            # Пытаемся загрузить ког
            try:
                await self.bot.load_extension(f'cogs.{cog_name}')

                embed = discord.Embed(
                    title="✅ Ког успешно загружен",
                    description=f"Ког `{cog_name}` был создан и загружен!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Файл", value=f"`{file_path}`", inline=False)
                embed.add_field(name="Размер кода", value=f"{len(code)} символов", inline=True)

                print(f"📥 Новый ког загружен: {cog_name} пользователем {interaction.user}")

            except Exception as e:
                # Удаляем файл если загрузка не удалась
                if os.path.exists(file_path):
                    os.remove(file_path)

                embed = discord.Embed(
                    title="❌ Ошибка загрузки кога",
                    description=f"Не удалось загрузить ког `{cog_name}`:",
                    color=discord.Color.red()
                )
                embed.add_field(name="Ошибка", value=f"```{str(e)}```", inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Неизвестная ошибка",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="reload_cog", description="Перезагрузить существующий ког (только для владельца)")
    @app_commands.describe(
        cog_name="Название кога для перезагрузки",
        code="Новый код Python для кога"
    )
    @is_admin_or_owner()
    async def reload_cog(self, interaction: discord.Interaction, cog_name: str, code: str):
        """Перезагрузить существующий ког с новым кодом"""
        try:
            file_path = f'./cogs/{cog_name}.py'

            # Проверяем существование кога
            if not os.path.exists(file_path):
                embed = discord.Embed(
                    title="❌ Ког не найден",
                    description=f"Ког `{cog_name}` не существует! Используйте `/load_cog` для создания нового.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Сохраняем новый код в файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            # Пытаемся перезагрузить ког
            try:
                # Сначала выгружаем, если загружен
                if f'cogs.{cog_name}' in self.bot.extensions:
                    await self.bot.unload_extension(f'cogs.{cog_name}')

                # Загружаем новую версию
                await self.bot.load_extension(f'cogs.{cog_name}')

                embed = discord.Embed(
                    title="✅ Ког успешно перезагружен",
                    description=f"Ког `{cog_name}` был обновлен и перезагружен!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Файл", value=f"`{file_path}`", inline=False)
                embed.add_field(name="Размер кода", value=f"{len(code)} символов", inline=True)

                print(f"🔄 Ког перезагружен: {cog_name} пользователем {interaction.user}")

            except Exception as e:
                embed = discord.Embed(
                    title="❌ Ошибка перезагрузки кога",
                    description=f"Не удалось перезагрузить ког `{cog_name}`:",
                    color=discord.Color.red()
                )
                embed.add_field(name="Ошибка", value=f"```{str(e)}```", inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Неизвестная ошибка",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="delete_cog", description="Удалить ког (только для владельца)")
    @app_commands.describe(cog_name="Название кога для удаления")
    @is_admin_or_owner()
    async def delete_cog(self, interaction: discord.Interaction, cog_name: str):
        """Удалить ког"""
        try:
            file_path = f'./cogs/{cog_name}.py'

            # Проверяем существование кога
            if not os.path.exists(file_path):
                embed = discord.Embed(
                    title="❌ Ког не найден",
                    description=f"Ког `{cog_name}` не существует!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Защита от удаления системных когов
            protected_cogs = ['cog_manager', 'shutdown', 'shutdown_confirm']
            if cog_name in protected_cogs:
                embed = discord.Embed(
                    title="❌ Нельзя удалить системный ког",
                    description="Этот ког необходим для работы бота!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Выгружаем ког если он загружен
            if f'cogs.{cog_name}' in self.bot.extensions:
                await self.bot.unload_extension(f'cogs.{cog_name}')

            # Удаляем файл
            os.remove(file_path)

            embed = discord.Embed(
                title="✅ Ког удален",
                description=f"Ког `{cog_name}` был успешно удален!",
                color=discord.Color.green()
            )

            print(f"🗑️ Ког удален: {cog_name} пользователем {interaction.user}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка удаления",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="list_cogs", description="Показать список всех когов (только для владельца)")
    @is_admin_or_owner()
    async def list_cogs(self, interaction: discord.Interaction):
        """Показать список всех когов"""
        try:
            cogs_dir = './cogs'
            if not os.path.exists(cogs_dir):
                embed = discord.Embed(
                    title="📚 Список когов",
                    description="Папка с когами не существует!",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Получаем все файлы когов
            cog_files = [f for f in os.listdir(cogs_dir) if f.endswith('.py') and not f.startswith('__')]

            if not cog_files:
                embed = discord.Embed(
                    title="📚 Список когов",
                    description="Коги не найдены!",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            loaded_cogs = []
            unloaded_cogs = []

            for cog_file in cog_files:
                cog_name = cog_file[:-3]  # Убираем .py
                if f'cogs.{cog_name}' in self.bot.extensions:
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

            embed.add_field(
                name="📋 Команды управления",
                value=(
                    "`/load_cog <имя> <код>` - создать и загрузить новый ког\n"
                    "`/reload_cog <имя> <код>` - обновить и перезагрузить ког\n"
                    "`/delete_cog <имя>` - удалить ког\n"
                    "`/list_cogs` - показать этот список\n"
                    "`/get_cog_info <имя>` - показать информацию о коге"
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

    @app_commands.command(name="get_cog_info", description="Показать информацию о коге (только для владельца)")
    @app_commands.describe(cog_name="Название кога")
    @is_admin_or_owner()
    async def get_cog_info(self, interaction: discord.Interaction, cog_name: str):
        """Показать информацию о конкретном коге"""
        try:
            file_path = f'./cogs/{cog_name}.py'

            if not os.path.exists(file_path):
                embed = discord.Embed(
                    title="❌ Ког не найден",
                    description=f"Ког `{cog_name}` не существует!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Читаем содержимое файла
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Получаем информацию о файле
            file_stats = os.stat(file_path)
            file_size = file_stats.st_size
            modified_time = file_stats.st_mtime

            is_loaded = f'cogs.{cog_name}' in self.bot.extensions

            embed = discord.Embed(
                title=f"📄 Информация о коге: {cog_name}",
                color=discord.Color.blue()
            )

            embed.add_field(name="🔄 Статус", value="🟢 Загружен" if is_loaded else "🔴 Не загружен", inline=True)
            embed.add_field(name="📏 Размер", value=f"{file_size} байт", inline=True)
            embed.add_field(name="📝 Строк кода", value=f"{len(content.splitlines())}", inline=True)

            embed.add_field(
                name="📅 Последнее изменение",
                value=f"<t:{int(modified_time)}:R>",
                inline=False
            )

            # Показываем первые 10 строк кода
            preview_lines = content.splitlines()[:10]
            preview = '\n'.join(preview_lines)
            if len(content.splitlines()) > 10:
                preview += "\n..."

            embed.add_field(
                name="👀 Предпросмотр кода",
                value=f"```python\n{preview[:1000]}\n```",
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

    # Обработчик ошибок для команд
    @load_cog.error
    @reload_cog.error
    @delete_cog.error
    @list_cogs.error
    @get_cog_info.error
    async def cog_manager_error(self, interaction: discord.Interaction, error):
        """Обработчик ошибок для команд управления когами"""
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
    await bot.add_cog(CogManager(bot))