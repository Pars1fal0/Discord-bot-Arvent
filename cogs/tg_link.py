import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
from typing import Dict, List, Optional
import datetime

from cogs.shutdown import is_admin_or_owner


def is_bot_owner():
    """Проверка на владельца бота"""

    async def predicate(interaction: discord.Interaction) -> bool:
        return await interaction.client.is_owner(interaction.user)

    return app_commands.check(predicate)


class TelegramBridge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = 'telegram_bridge_config.json'
        self.config = self.load_config()
        self.session = None
        self.last_processed_message = None  # Чтобы избежать дублирования

    def load_config(self) -> Dict:
        """Загрузка конфигурации из файла"""
        default_config = {
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "discord_log_channel_id": "",  # Специально для канала логов
            "enabled": False,
            "forward_discord_to_telegram": True,
            "include_bot_messages": True,  # Включать сообщения от ботов
            "include_system_messages": True,  # Включать системные сообщения
            "message_format": "detailed"  # detailed или simple
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # Обновляем старый конфиг, добавляя отсутствующие ключи
                for key, value in default_config.items():
                    if key not in loaded_config:
                        loaded_config[key] = value

                # Сохраняем обновленный конфиг
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(loaded_config, f, indent=4, ensure_ascii=False)

                return loaded_config
            else:
                # Создаем файл с дефолтными настройками
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                return default_config
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return default_config

    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации: {e}")
            return False

    async def send_telegram_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Отправка сообщения в Telegram"""
        if not self.config["telegram_bot_token"] or not self.config["telegram_chat_id"]:
            return False

        if self.session is None:
            self.session = aiohttp.ClientSession()

        url = f"https://api.telegram.org/bot{self.config['telegram_bot_token']}/sendMessage"

        # Разбиваем длинные сообщения на части (Telegram имеет лимит 4096 символов)
        if len(text) > 4000:
            parts = [text[i:i + 4000] for i in range(0, len(text), 4000)]
            success = True
            for part in parts:
                payload = {
                    "chat_id": self.config["telegram_chat_id"],
                    "text": part,
                    "parse_mode": parse_mode
                }
                try:
                    async with self.session.post(url, json=payload) as response:
                        if response.status != 200:
                            success = False
                except Exception:
                    success = False
            return success
        else:
            payload = {
                "chat_id": self.config["telegram_chat_id"],
                "text": text,
                "parse_mode": parse_mode
            }

            try:
                async with self.session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ Ошибка отправки в Telegram: {error_text}")
                        return False
            except Exception as e:
                print(f"❌ Ошибка соединения с Telegram: {e}")
                return False

    def format_discord_message(self, message) -> str:
        """Форматирование сообщения Discord для Telegram"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Используем get с значением по умолчанию на случай отсутствия ключа
        message_format = self.config.get("message_format", "detailed")

        if message_format == "simple":
            # Простой формат
            if message.author.bot:
                author = f"🤖 {message.author.display_name}"
            else:
                author = f"👤 {message.author.display_name}"

            text = f"{author}: {message.content}"

        else:
            # Детальный формат
            if message.author.bot:
                author = f"<b>🤖 БОТ: {message.author.display_name}</b>"
            else:
                author = f"<b>👤 {message.author.display_name}</b>"

            channel = f"<i>#{message.channel.name}</i>"
            time = f"<code>{timestamp}</code>"

            text = f"{author} в {channel}\n"
            text += f"Время: {time}\n"

            if message.content:
                text += f"\n💬 {message.content}"

        # Добавляем информацию о вложениях
        if message.attachments:
            attachments_info = []
            for attachment in message.attachments:
                file_type = "📎 Файл"
                if any(attachment.filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                    file_type = "🖼️ Изображение"
                elif any(attachment.filename.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov']):
                    file_type = "🎥 Видео"
                elif any(attachment.filename.lower().endswith(ext) for ext in ['.mp3', '.wav', '.ogg']):
                    file_type = "🔊 Аудио"

                attachments_info.append(f"{file_type}: {attachment.filename} ({attachment.size} bytes)")

            text += f"\n\n📁 Вложения ({len(message.attachments)}):\n" + "\n".join(attachments_info)

        # Добавляем информацию об эмбедах
        if message.embeds:
            text += f"\n\n🔗 Эмбеды: {len(message.embeds)}"
            for embed in message.embeds:
                if embed.title:
                    text += f"\n- Заголовок: {embed.title}"
                if embed.description:
                    desc = embed.description[:100] + "..." if len(embed.description) > 100 else embed.description
                    text += f"\n- Описание: {desc}"

        # Добавляем информацию о стикерах
        if message.stickers:
            text += f"\n\n🎨 Стикеры: {len(message.stickers)}"
            for sticker in message.stickers:
                text += f"\n- {sticker.name}"

        return text

    @commands.Cog.listener()
    async def on_message(self, message):
        """Обработка сообщений из Discord для отправки в Telegram"""
        # Используем get с значениями по умолчанию для всех ключей
        if not self.config.get("enabled", False) or not self.config.get("forward_discord_to_telegram", True):
            return

        # Проверяем, что сообщение из нужного канала логов
        discord_log_channel_id = self.config.get("discord_log_channel_id", "")
        if not discord_log_channel_id:
            return

        if str(message.channel.id) != str(discord_log_channel_id):
            return

        # Проверяем, не обрабатывали ли мы уже это сообщение (анти-дублирование)
        if self.last_processed_message == message.id:
            return

        self.last_processed_message = message.id

        # Форматируем и отправляем сообщение
        telegram_text = self.format_discord_message(message)

        # Отправляем в Telegram
        success = await self.send_telegram_message(telegram_text)

        if not success:
            print(f"❌ Не удалось отправить сообщение {message.id} в Telegram")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Обработка редактированных сообщений"""
        if not self.config.get("enabled", False) or not self.config.get("forward_discord_to_telegram", True):
            return

        discord_log_channel_id = self.config.get("discord_log_channel_id", "")
        if not discord_log_channel_id:
            return

        if str(after.channel.id) != str(discord_log_channel_id):
            return

        # Отправляем уведомление о редактировании
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        telegram_text = f"✏️ <b>СООБЩЕНИЕ ОТРЕДАКТИРОВАНО</b>\n"
        telegram_text += f"👤 <b>{after.author.display_name}</b>\n"
        telegram_text += f"📅 <code>{timestamp}</code>\n\n"
        telegram_text += f"<b>Было:</b>\n<code>{before.content if before.content else '[без текста]'}</code>\n\n"
        telegram_text += f"<b>Стало:</b>\n<code>{after.content if after.content else '[без текста]'}</code>"

        await self.send_telegram_message(telegram_text)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Обработка удаленных сообщений"""
        if not self.config.get("enabled", False) or not self.config.get("forward_discord_to_telegram", True):
            return

        discord_log_channel_id = self.config.get("discord_log_channel_id", "")
        if not discord_log_channel_id:
            return

        if str(message.channel.id) != str(discord_log_channel_id):
            return

        # Отправляем уведомление об удалении
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        telegram_text = f"🗑️ <b>СООБЩЕНИЕ УДАЛЕНО</b>\n"
        telegram_text += f"👤 <b>{message.author.display_name}</b>\n"
        telegram_text += f"📅 <code>{timestamp}</code>\n\n"
        telegram_text += f"<b>Содержимое:</b>\n<code>{message.content if message.content else '[без текста]'}</code>"

        await self.send_telegram_message(telegram_text)

    @app_commands.command(name="setup_logs_bridge",
                          description="Настроить мост для логов между Discord и Telegram (только для владельца)")
    @app_commands.describe(
        bot_token="Токен Telegram бота",
        chat_id="ID чата в Telegram для логов",
        log_channel="Канал Discord с логами"
    )
    @is_admin_or_owner()
    async def setup_logs_bridge(self, interaction: discord.Interaction, bot_token: str, chat_id: str,
                                log_channel: discord.TextChannel):
        """Настроить мост для логов между Discord и Telegram"""
        try:
            self.config["telegram_bot_token"] = bot_token
            self.config["telegram_chat_id"] = chat_id
            self.config["discord_log_channel_id"] = str(log_channel.id)
            self.config["enabled"] = True
            self.config["include_bot_messages"] = True
            self.config["include_system_messages"] = True
            self.config["message_format"] = "detailed"  # Убедимся, что ключ существует

            if self.save_config():
                # Тестируем соединение с Telegram
                test_message = "🔗 <b>Мост для логов Discord-Telegram активирован!</b>\n\nТестовое сообщение. Все сообщения из канала логов будут пересылаться сюда."
                success = await self.send_telegram_message(test_message)

                embed = discord.Embed(
                    title="✅ Мост для логов настроен",
                    color=discord.Color.green()
                )
                embed.add_field(name="Telegram Chat ID", value=chat_id, inline=True)
                embed.add_field(name="Discord Log Channel", value=log_channel.mention, inline=True)
                embed.add_field(name="Статус Telegram", value="✅ Подключен" if success else "❌ Ошибка", inline=True)
                embed.add_field(name="Пересылка ботов", value="✅ Включена", inline=True)
                embed.add_field(name="Формат", value="Детальный", inline=True)

                if not success:
                    embed.add_field(
                        name="⚠️ Внимание",
                        value="Не удалось отправить тестовое сообщение в Telegram. Проверьте токен и ID чата.",
                        inline=False
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не удалось сохранить настройки!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка настройки",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="logs_bridge_status",
                          description="Показать статус моста для логов (только для владельца)")
    @is_admin_or_owner()
    async def logs_bridge_status(self, interaction: discord.Interaction):
        """Показать статус моста для логов"""
        embed = discord.Embed(
            title="🌉 Статус моста для логов Discord-Telegram",
            color=discord.Color.blue()
        )

        embed.add_field(name="🔄 Статус", value="✅ Включен" if self.config.get("enabled", False) else "❌ Выключен",
                        inline=True)
        embed.add_field(name="Discord → Telegram", value="✅ Включено", inline=True)
        embed.add_field(name="🤖 Сообщения ботов",
                        value="✅ Включены" if self.config.get("include_bot_messages", True) else "❌ Выключены",
                        inline=True)

        if self.config.get("telegram_bot_token"):
            embed.add_field(name="🤖 Telegram Bot", value="✅ Настроен", inline=True)
        else:
            embed.add_field(name="🤖 Telegram Bot", value="❌ Не настроен", inline=True)

        if self.config.get("telegram_chat_id"):
            embed.add_field(name="💬 Telegram Chat", value="✅ Настроен", inline=True)
        else:
            embed.add_field(name="💬 Telegram Chat", value="❌ Не настроен", inline=True)

        discord_log_channel_id = self.config.get("discord_log_channel_id")
        if discord_log_channel_id:
            channel = self.bot.get_channel(int(discord_log_channel_id))
            if channel:
                embed.add_field(name="📋 Канал логов", value=channel.mention, inline=True)
            else:
                embed.add_field(name="📋 Канал логов", value="❌ Не найден", inline=True)
        else:
            embed.add_field(name="📋 Канал логов", value="❌ Не настроен", inline=True)

        message_format = self.config.get("message_format", "detailed")
        embed.add_field(name="📝 Формат", value="Детальный" if message_format == "detailed" else "Простой", inline=True)

        # Тестируем соединение с Telegram
        if self.config.get("enabled", False) and self.config.get("telegram_bot_token"):
            test_success = await self.send_telegram_message("🔍 <b>Проверка связи моста логов...</b>")
            embed.add_field(name="📡 Соединение с Telegram", value="✅ Работает" if test_success else "❌ Ошибка",
                            inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="enable_logs_bridge", description="Включить мост для логов (только для владельца)")
    @is_admin_or_owner()
    async def enable_logs_bridge(self, interaction: discord.Interaction):
        """Включить мост для логов"""
        self.config["enabled"] = True
        if self.save_config():
            embed = discord.Embed(
                title="✅ Мост для логов включен",
                description="Мост между Discord и Telegram для логов теперь активен!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось сохранить настройки!",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="disable_logs_bridge", description="Выключить мост для логов (только для владельца)")
    @is_admin_or_owner()
    async def disable_logs_bridge(self, interaction: discord.Interaction):
        """Выключить мост для логов"""
        self.config["enabled"] = False
        if self.save_config():
            embed = discord.Embed(
                title="✅ Мост для логов выключен",
                description="Мост между Discord и Telegram для логов теперь отключен!",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось сохранить настройки!",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="send_test_log",
                          description="Отправить тестовое сообщение в Telegram (только для владельца)")
    @app_commands.describe(message="Тестовое сообщение")
    @is_admin_or_owner()
    async def send_test_log(self, interaction: discord.Interaction, message: str):
        """Отправить тестовое сообщение в Telegram"""
        if not self.config.get("enabled", False):
            embed = discord.Embed(
                title="❌ Мост отключен",
                description="Сначала включите мост с помощью `/enable_logs_bridge`",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        telegram_text = f"🧪 <b>ТЕСТОВОЕ СООБЩЕНИЕ ИЗ DISCORD</b>\n\n<code>{message}</code>"
        success = await self.send_telegram_message(telegram_text)

        if success:
            embed = discord.Embed(
                title="✅ Тестовое сообщение отправлено в Telegram",
                description=message,
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка отправки",
                description="Не удалось отправить тестовое сообщение в Telegram. Проверьте настройки моста.",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_logs_channel", description="Установить канал для логов (только для владельца)")
    @app_commands.describe(channel="Канал Discord с логами")
    @is_admin_or_owner()
    async def set_logs_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Установить канал для логов"""
        self.config["discord_log_channel_id"] = str(channel.id)
        if self.save_config():
            embed = discord.Embed(
                title="✅ Канал логов установлен",
                description=f"Канал для логов установлен: {channel.mention}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось сохранить настройки!",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_message_format", description="Установить формат сообщений (только для владельца)")
    @app_commands.describe(format="Формат сообщений (detailed или simple)")
    @is_admin_or_owner()
    async def set_message_format(self, interaction: discord.Interaction, format: str):
        """Установить формат сообщений"""
        if format.lower() not in ["detailed", "simple"]:
            embed = discord.Embed(
                title="❌ Неверный формат",
                description="Доступные форматы: detailed, simple",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.config["message_format"] = format.lower()
        if self.save_config():
            embed = discord.Embed(
                title="✅ Формат сообщений установлен",
                description=f"Формат сообщений изменен на: {format}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось сохранить настройки!",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Инициализация при готовности бота"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        log_channel_info = "не настроен"
        discord_log_channel_id = self.config.get("discord_log_channel_id")
        if discord_log_channel_id:
            channel = self.bot.get_channel(int(discord_log_channel_id))
            if channel:
                log_channel_info = f"#{channel.name}"

        print(
            f"🌉 Telegram Bridge для логов готов! Статус: {'✅ Включен' if self.config.get('enabled', False) else '❌ Выключен'}")
        print(f"📋 Канал логов: {log_channel_info}")

    def cog_unload(self):
        """Очистка при выгрузке кога"""
        if self.session:
            asyncio.create_task(self.session.close())

    # Обработчик ошибок для команд
    @setup_logs_bridge.error
    @logs_bridge_status.error
    @enable_logs_bridge.error
    @disable_logs_bridge.error
    @send_test_log.error
    @set_logs_channel.error
    @set_message_format.error
    async def telegram_bridge_error(self, interaction: discord.Interaction, error):
        """Обработчик ошибок для команд моста"""
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
    await bot.add_cog(TelegramBridge(bot))