import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from typing import Dict, List, Optional
import datetime


class TempVoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_channels = {}  # {channel_id: {owner_id, parent_id, settings}}
        self.voice_creators = {}  # {guild_id: creator_channel_id}
        self.setup_messages = {}  # {message_id: channel_id}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Обработка событий голосовых каналов"""
        # Пользователь зашел в голосовой канал
        if after.channel and after.channel.id in self.voice_creators.values():
            await self.create_temp_channel(member, after.channel)

        # Пользователь вышел из голосового канала
        if before.channel and before.channel.id in self.temp_channels:
            await self.check_empty_channel(before.channel)

        # Пользователь перешел между каналами
        if before.channel and after.channel and before.channel.id in self.temp_channels:
            await self.check_empty_channel(before.channel)

    async def create_temp_channel(self, member, creator_channel):
        """Создание временного голосового канала"""
        guild = member.guild
        category = creator_channel.category

        # Находим свободный номер для канала
        channel_number = 1
        while f"Комната {member.display_name} #{channel_number}" in [ch.name for ch in guild.voice_channels]:
            channel_number += 1

        channel_name = f"Комната {member.display_name} #{channel_number}"

        # Создаем канал
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
                member: discord.PermissionOverwrite(manage_channels=True, manage_roles=True, move_members=True)
            }

            temp_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )

            # Сохраняем информацию о канале
            self.temp_channels[temp_channel.id] = {
                "owner_id": member.id,
                "parent_id": creator_channel.id,
                "settings": {
                    "name": channel_name,
                    "user_limit": 0,
                    "bitrate": guild.bitrate_limit,
                    "locked": False,
                    "hidden": False
                }
            }

            # Перемещаем пользователя в новый канал
            await member.move_to(temp_channel)

            # Отправляем сообщение с настройками
            await self.send_settings_embed(temp_channel, member)

        except Exception as e:
            print(f"Ошибка при создании канала: {e}")

    async def send_settings_embed(self, channel, owner):
        """Отправка embed с настройками канала"""
        settings = self.temp_channels[channel.id]["settings"]

        embed = discord.Embed(
            title="⚙️ Настройки голосового канала",
            description=f"Владелец: {owner.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )

        embed.add_field(
            name="📝 Название",
            value=f"`{settings['name']}`",
            inline=True
        )

        embed.add_field(
            name="👥 Лимит пользователей",
            value=f"`{settings['user_limit'] if settings['user_limit'] > 0 else 'Без лимита'}`",
            inline=True
        )

        embed.add_field(
            name="🔒 Статус",
            value=f"`{'🔐 Закрыт' if settings['locked'] else '🔓 Открыт'}`",
            inline=True
        )

        embed.add_field(
            name="🌐 Качество звука",
            value=f"`{settings['bitrate'] // 1000}kbps`",
            inline=True
        )

        embed.add_field(
            name="👻 Видимость",
            value=f"`{'Скрыт' if settings['hidden'] else 'Видим'}`",
            inline=True
        )

        embed.set_footer(text="Используйте кнопки ниже для настройки")

        view = ChannelSettingsView(self, channel.id)
        message = await owner.send(embed=embed, view=view)
        self.setup_messages[message.id] = channel.id

    async def update_settings_embed(self, channel_id):
        """Обновление embed сообщения с настройками"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        settings = self.temp_channels[channel_id]["settings"]
        owner = channel.guild.get_member(self.temp_channels[channel_id]["owner_id"])

        if not owner:
            return

        # Находим сообщение для обновления
        message_id_to_remove = []
        for msg_id, ch_id in self.setup_messages.items():
            if ch_id == channel_id:
                try:
                    message = await owner.fetch_message(msg_id)

                    embed = discord.Embed(
                        title="⚙️ Настройки голосового канала",
                        description=f"Владелец: {owner.mention}",
                        color=discord.Color.green(),
                        timestamp=datetime.datetime.now()
                    )

                    embed.add_field(
                        name="📝 Название",
                        value=f"`{settings['name']}`",
                        inline=True
                    )

                    embed.add_field(
                        name="👥 Лимит пользователей",
                        value=f"`{settings['user_limit'] if settings['user_limit'] > 0 else 'Без лимита'}`",
                        inline=True
                    )

                    embed.add_field(
                        name="🔒 Статус",
                        value=f"`{'🔐 Закрыт' if settings['locked'] else '🔓 Открыт'}`",
                        inline=True
                    )

                    embed.add_field(
                        name="🌐 Качество звука",
                        value=f"`{settings['bitrate'] // 1000}kbps`",
                        inline=True
                    )

                    embed.add_field(
                        name="👻 Видимость",
                        value=f"`{'Скрыт' if settings['hidden'] else 'Видим'}`",
                        inline=True
                    )

                    embed.set_footer(text="Используйте кнопки ниже для настройки")

                    view = ChannelSettingsView(self, channel_id)
                    await message.edit(embed=embed, view=view)

                except discord.NotFound:
                    message_id_to_remove.append(msg_id)
                except Exception as e:
                    print(f"Ошибка при обновлении сообщения: {e}")

        # Удаляем несуществующие сообщения
        for msg_id in message_id_to_remove:
            self.setup_messages.pop(msg_id, None)

    async def check_empty_channel(self, channel):
        """Проверка пустых каналов и их удаление"""
        if channel.id not in self.temp_channels:
            return

        # Если в канале никого нет - удаляем
        if len(channel.members) == 0:
            try:
                # Удаляем сообщения настроек
                message_ids_to_remove = []
                for msg_id, ch_id in self.setup_messages.items():
                    if ch_id == channel.id:
                        message_ids_to_remove.append(msg_id)

                for msg_id in message_ids_to_remove:
                    self.setup_messages.pop(msg_id, None)

                # Удаляем канал
                await channel.delete()
                self.temp_channels.pop(channel.id)

            except Exception as e:
                print(f"Ошибка при удалении канала: {e}")

    @app_commands.command(name="setup_temp_voice", description="Настройка системы временных голосовых каналов")
    @app_commands.describe(channel_name="Название канала-создателя (по умолчанию: '➕ Создать комнату')")
    @app_commands.default_permissions(administrator=True)
    async def setup_temp_voice(self, interaction: discord.Interaction, channel_name: str = "➕ Создать комнату"):
        """Настройка системы временных голосовых каналов"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Создаем канал-создатель
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
                interaction.guild.me: discord.PermissionOverwrite(manage_channels=True)
            }

            creator_channel = await interaction.guild.create_voice_channel(
                name=channel_name,
                category=interaction.channel.category,
                overwrites=overwrites
            )

            self.voice_creators[interaction.guild.id] = creator_channel.id

            embed = discord.Embed(
                title="✅ Система временных голосовых каналов настроена!",
                description=f"Канал-создатель: {creator_channel.mention}",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Как использовать:",
                value="1. Зайдите в канал-создатель\n2. Автоматически создастся ваша комната\n3. Настройте её через ЛС бота",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при настройке: {e}", ephemeral=True)

    @app_commands.command(name="temp_voice_info", description="Информация о системе временных голосовых каналов")
    async def temp_voice_info(self, interaction: discord.Interaction):
        """Информация о системе временных голосовых каналов"""
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="🎤 Система временных голосовых каналов",
            color=discord.Color.blue()
        )

        if interaction.guild.id in self.voice_creators:
            creator_channel = interaction.guild.get_channel(self.voice_creators[interaction.guild.id])
            if creator_channel:
                embed.add_field(
                    name="Канал-создатель",
                    value=creator_channel.mention,
                    inline=True
                )

                # Считаем активные комнаты
                active_rooms = sum(
                    1 for ch_id, data in self.temp_channels.items()
                    if data["parent_id"] == creator_channel.id
                )
                embed.add_field(
                    name="Активных комнат",
                    value=active_rooms,
                    inline=True
                )
            else:
                embed.add_field(
                    name="Статус",
                    value="❌ Канал-создатель не найден",
                    inline=True
                )
        else:
            embed.add_field(
                name="Статус",
                value="❌ Система не настроена",
                inline=True
            )

        embed.add_field(
            name="Как использовать:",
            value="1. Зайдите в канал-создатель\n2. Автоматически создастся ваша комната\n3. Настройте её через ЛС бота",
            inline=False
        )

        embed.add_field(
            name="Возможности:",
            value="• Изменение названия\n• Установка лимита пользователей\n• Настройка качества звука\n• Блокировка/разблокировка\n• Скрытие/отображение",
            inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="transfer_ownership", description="Передать владение голосовой комнатой")
    @app_commands.describe(new_owner="Новый владелец комнаты")
    async def transfer_ownership(self, interaction: discord.Interaction, new_owner: discord.Member):
        """Передать владение голосовой комнатой"""
        await interaction.response.defer(ephemeral=True)

        # Находим канал, где пользователь является владельцем
        user_channel = None
        for channel_id, data in self.temp_channels.items():
            if data["owner_id"] == interaction.user.id:
                user_channel = interaction.guild.get_channel(channel_id)
                break

        if not user_channel:
            await interaction.followup.send("❌ Вы не являетесь владельцем голосовой комнаты!", ephemeral=True)
            return

        if new_owner.bot:
            await interaction.followup.send("❌ Нельзя передать владение боту!", ephemeral=True)
            return

        # Обновляем владельца
        self.temp_channels[user_channel.id]["owner_id"] = new_owner.id

        # Обновляем права
        overwrites = user_channel.overwrites
        overwrites[interaction.user] = discord.PermissionOverwrite(connect=True, view_channel=True)
        overwrites[new_owner] = discord.PermissionOverwrite(manage_channels=True, manage_roles=True, move_members=True)

        await user_channel.edit(overwrites=overwrites)
        await self.update_settings_embed(user_channel.id)

        embed = discord.Embed(
            title="✅ Владение передано",
            description=f"Владелец комнаты {user_channel.mention} теперь {new_owner.mention}",
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # Методы для изменения настроек
    async def rename_channel(self, channel_id, new_name):
        """Изменение названия канала"""
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.edit(name=new_name)
            self.temp_channels[channel_id]["settings"]["name"] = new_name
            await self.update_settings_embed(channel_id)

    async def set_user_limit(self, channel_id, limit):
        """Установка лимита пользователей"""
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.edit(user_limit=limit)
            self.temp_channels[channel_id]["settings"]["user_limit"] = limit
            await self.update_settings_embed(channel_id)

    async def set_bitrate(self, channel_id, bitrate):
        """Установка качества звука"""
        channel = self.bot.get_channel(channel_id)
        if channel:
            max_bitrate = channel.guild.bitrate_limit
            actual_bitrate = min(bitrate, max_bitrate)
            await channel.edit(bitrate=actual_bitrate)
            self.temp_channels[channel_id]["settings"]["bitrate"] = actual_bitrate
            await self.update_settings_embed(channel_id)

    async def toggle_lock(self, channel_id):
        """Переключение блокировки канала"""
        channel = self.bot.get_channel(channel_id)
        if channel:
            settings = self.temp_channels[channel_id]["settings"]
            settings["locked"] = not settings["locked"]

            overwrites = channel.overwrites
            if settings["locked"]:
                overwrites[channel.guild.default_role] = discord.PermissionOverwrite(connect=False, view_channel=True)
            else:
                overwrites[channel.guild.default_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

            await channel.edit(overwrites=overwrites)
            await self.update_settings_embed(channel_id)

    async def toggle_hidden(self, channel_id):
        """Переключение видимости канала"""
        channel = self.bot.get_channel(channel_id)
        if channel:
            settings = self.temp_channels[channel_id]["settings"]
            settings["hidden"] = not settings["hidden"]

            overwrites = channel.overwrites
            if settings["hidden"]:
                overwrites[channel.guild.default_role] = discord.PermissionOverwrite(connect=False, view_channel=False)
            else:
                overwrites[channel.guild.default_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

            await channel.edit(overwrites=overwrites)
            await self.update_settings_embed(channel_id)


class ChannelSettingsView(discord.ui.View):
    """View с кнопками для настройки голосового канала"""

    def __init__(self, cog, channel_id, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="📝 Переименовать", style=discord.ButtonStyle.primary)
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для переименования канала"""
        modal = RenameModal(self.cog, self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👥 Лимит", style=discord.ButtonStyle.secondary)
    async def limit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для установки лимита пользователей"""
        modal = LimitModal(self.cog, self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🌐 Качество", style=discord.ButtonStyle.secondary)
    async def bitrate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для настройки качества звука"""
        modal = BitrateModal(self.cog, self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔒 Заблокировать", style=discord.ButtonStyle.danger)
    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для блокировки/разблокировки канала"""
        await self.cog.toggle_lock(self.channel_id)
        await interaction.response.defer()

    @discord.ui.button(label="👻 Скрыть", style=discord.ButtonStyle.danger)
    async def hide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для скрытия/отображения канала"""
        await self.cog.toggle_hidden(self.channel_id)
        await interaction.response.defer()


class RenameModal(discord.ui.Modal, title="Переименовать канал"):
    """Модальное окно для ввода нового названия"""

    def __init__(self, cog, channel_id):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id

    new_name = discord.ui.TextInput(
        label="Новое название",
        placeholder="Введите новое название канала...",
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.rename_channel(self.channel_id, self.new_name.value)
        await interaction.response.send_message(f"✅ Название изменено на: `{self.new_name.value}`", ephemeral=True)


class LimitModal(discord.ui.Modal, title="Установить лимит пользователей"):
    """Модальное окно для установки лимита пользователей"""

    def __init__(self, cog, channel_id):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id

    user_limit = discord.ui.TextInput(
        label="Лимит пользователей (0 - без лимита)",
        placeholder="Введите число от 0 до 99...",
        max_length=2
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.user_limit.value)
            if limit < 0 or limit > 99:
                await interaction.response.send_message("❌ Лимит должен быть от 0 до 99", ephemeral=True)
                return

            await self.cog.set_user_limit(self.channel_id, limit)
            await interaction.response.send_message(
                f"✅ Лимит пользователей установлен: `{limit if limit > 0 else 'Без лимита'}`", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Введите корректное число", ephemeral=True)


class BitrateModal(discord.ui.Modal, title="Настройка качества звука"):
    """Модальное окно для настройки качества звука"""

    def __init__(self, cog, channel_id):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id

    bitrate = discord.ui.TextInput(
        label="Качество звука (в kbps)",
        placeholder="Введите значение от 8 до 96...",
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bitrate_kbps = int(self.bitrate.value)
            bitrate_bps = bitrate_kbps * 1000

            # Проверяем допустимые значения
            if bitrate_kbps < 8 or bitrate_kbps > 96:
                await interaction.response.send_message("❌ Качество должно быть от 8 до 96 kbps", ephemeral=True)
                return

            await self.cog.set_bitrate(self.channel_id, bitrate_bps)
            await interaction.response.send_message(f"✅ Качество звука установлено: `{bitrate_kbps}kbps`",
                                                    ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Введите корректное число", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TempVoiceCog(bot))