import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
from typing import Dict, List, Optional

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

    def load_config(self) -> Dict:
        """Загрузка конфигурации из файла"""
        default_config = {
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "discord_channel_id": "",
            "enabled": False,
            "forward_discord_to_telegram": True,
            "forward_telegram_to_discord": True,
            "webhook_url": "",
            "webhook_secret": ""
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
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

    async def get_telegram_updates(self) -> List[Dict]:
        """Получение обновлений из Telegram"""
        if not self.config["telegram_bot_token"]:
            return []

        if self.session is None:
            self.session = aiohttp.ClientSession()

        url = f"https://api.telegram.org/bot{self.config['telegram_bot_token']}/getUpdates"

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result", [])
                else:
                    return []
        except Exception as e:
            print(f"❌ Ошибка получения обновлений из Telegram: {e}")
            return []

    @commands.Cog.listener()
    async def on_message(self, message):
        """Обработка сообщений из Discord для отправки в Telegram"""
        if not self.config["enabled"] or not self.config["forward_discord_to_telegram"]:
            return

        # Игнорируем сообщения от ботов
        if message.author.bot:
            return

        # Если указан конкретный канал, проверяем его
        if self.config["discord_channel_id"]:
            if str(message.channel.id) != str(self.config["discord_channel_id"]):
                return

        # Форматируем сообщение для Telegram
        if message.content:
            telegram_text = f"<b>💬 Discord:</b> {message.author.display_name}\n"
            telegram_text += f"<code>{message.content}</code>"

            if message.attachments:
                telegram_text += f"\n\n📎 <i>Вложения: {len(message.attachments)}</i>"

            # Отправляем в Telegram
            await self.send_telegram_message(telegram_text)

    @app_commands.command(name="setup_telegram_bridge",
                          description="Настроить мост между Discord и Telegram (только для владельца)")
    @app_commands.describe(
        bot_token="Токен Telegram бота",
        chat_id="ID чата в Telegram",
        channel_id="ID канала в Discord (оставьте пустым для всех каналов)"
    )
    @is_admin_or_owner()
    async def setup_telegram_bridge(self, interaction: discord.Interaction, bot_token: str, chat_id: str,
                                    channel_id: str = ""):
        """Настроить мост между Discord и Telegram"""
        try:
            self.config["telegram_bot_token"] = bot_token
            self.config["telegram_chat_id"] = chat_id
            self.config["discord_channel_id"] = channel_id
            self.config["enabled"] = True

            if self.save_config():
                # Тестируем соединение с Telegram
                test_message = "🔗 <b>Мост Discord-Telegram активирован!</b>\n\nТестовое сообщение из Discord."
                success = await self.send_telegram_message(test_message)

                embed = discord.Embed(
                    title="✅ Мост настроен",
                    color=discord.Color.green()
                )
                embed.add_field(name="Telegram Chat ID", value=chat_id, inline=True)
                embed.add_field(name="Discord Channel", value=f"<#{channel_id}>" if channel_id else "Все каналы",
                                inline=True)
                embed.add_field(name="Статус Telegram", value="✅ Подключен" if success else "❌ Ошибка", inline=True)

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

    @app_commands.command(name="telegram_bridge_status", description="Показать статус моста (только для владельца)")
    @is_admin_or_owner()
    async def telegram_bridge_status(self, interaction: discord.Interaction):
        """Показать статус моста между Discord и Telegram"""
        embed = discord.Embed(
            title="🌉 Статус моста Discord-Telegram",
            color=discord.Color.blue()
        )

        embed.add_field(name="🔄 Статус", value="✅ Включен" if self.config["enabled"] else "❌ Выключен", inline=True)
        embed.add_field(name="Discord → Telegram",
                        value="✅ Включено" if self.config["forward_discord_to_telegram"] else "❌ Выключено",
                        inline=True)
        embed.add_field(name="Telegram → Discord",
                        value="✅ Включено" if self.config["forward_telegram_to_discord"] else "❌ Выключено",
                        inline=True)

        if self.config["telegram_bot_token"]:
            embed.add_field(name="🤖 Telegram Bot", value="✅ Настроен", inline=True)
        else:
            embed.add_field(name="🤖 Telegram Bot", value="❌ Не настроен", inline=True)

        if self.config["telegram_chat_id"]:
            embed.add_field(name="💬 Telegram Chat", value="✅ Настроен", inline=True)
        else:
            embed.add_field(name="💬 Telegram Chat", value="❌ Не настроен", inline=True)

        if self.config["discord_channel_id"]:
            embed.add_field(name="📱 Discord Channel", value=f"<#{self.config['discord_channel_id']}>", inline=True)
        else:
            embed.add_field(name="📱 Discord Channel", value="Все каналы", inline=True)

        # Тестируем соединение с Telegram
        if self.config["enabled"] and self.config["telegram_bot_token"]:
            test_success = await self.send_telegram_message("🔍 <b>Проверка связи...</b>")
            embed.add_field(name="📡 Соединение с Telegram", value="✅ Работает" if test_success else "❌ Ошибка",
                            inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="enable_telegram_bridge", description="Включить мост (только для владельца)")
    @is_admin_or_owner()
    async def enable_telegram_bridge(self, interaction: discord.Interaction):
        """Включить мост между Discord и Telegram"""
        self.config["enabled"] = True
        if self.save_config():
            embed = discord.Embed(
                title="✅ Мост включен",
                description="Мост между Discord и Telegram теперь активен!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось сохранить настройки!",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="disable_telegram_bridge", description="Выключить мост (только для владельца)")
    @is_admin_or_owner()
    async def disable_telegram_bridge(self, interaction: discord.Interaction):
        """Выключить мост между Discord и Telegram"""
        self.config["enabled"] = False
        if self.save_config():
            embed = discord.Embed(
                title="✅ Мост выключен",
                description="Мост между Discord и Telegram теперь отключен!",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось сохранить настройки!",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="send_to_telegram", description="Отправить сообщение в Telegram (только для владельца)")
    @app_commands.describe(message="Сообщение для отправки в Telegram")
    @is_admin_or_owner()
    async def send_to_telegram(self, interaction: discord.Interaction, message: str):
        """Отправить сообщение в Telegram"""
        if not self.config["enabled"]:
            embed = discord.Embed(
                title="❌ Мост отключен",
                description="Сначала включите мост с помощью `/enable_telegram_bridge`",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        telegram_text = f"<b>💬 Из Discord:</b>\n<code>{message}</code>"
        success = await self.send_telegram_message(telegram_text)

        if success:
            embed = discord.Embed(
                title="✅ Сообщение отправлено в Telegram",
                description=message,
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка отправки",
                description="Не удалось отправить сообщение в Telegram. Проверьте настройки моста.",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="get_telegram_updates",
                          description="Получить последние сообщения из Telegram (только для владельца)")
    @is_admin_or_owner()
    async def get_telegram_updates(self, interaction: discord.Interaction):
        """Получить последние сообщения из Telegram"""
        if not self.config["enabled"]:
            embed = discord.Embed(
                title="❌ Мост отключен",
                description="Сначала включите мост с помощью `/enable_telegram_bridge`",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        updates = await self.get_telegram_updates()

        if not updates:
            embed = discord.Embed(
                title="📭 Нет новых сообщений из Telegram",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Берем последние 5 сообщений
        recent_updates = updates[-5:]

        embed = discord.Embed(
            title=f"📨 Последние {len(recent_updates)} сообщений из Telegram",
            color=discord.Color.blue()
        )

        for update in recent_updates:
            if "message" in update and "text" in update["message"]:
                user = update["message"]["from"]
                user_name = user.get("first_name", "") + " " + user.get("last_name", "")
                text = update["message"]["text"][:100] + "..." if len(update["message"]["text"]) > 100 else \
                update["message"]["text"]

                embed.add_field(
                    name=f"👤 {user_name}",
                    value=f"```{text}```",
                    inline=False
                )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="set_discord_channel",
                          description="Установить канал Discord для моста (только для владельца)")
    @app_commands.describe(channel="Канал Discord для моста")
    @is_admin_or_owner()
    async def set_discord_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Установить канал Discord для моста"""
        self.config["discord_channel_id"] = str(channel.id)
        if self.save_config():
            embed = discord.Embed(
                title="✅ Канал установлен",
                description=f"Канал для моста установлен: {channel.mention}",
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
        print(f"🌉 Telegram Bridge готов! Статус: {'✅ Включен' if self.config['enabled'] else '❌ Выключен'}")

    def cog_unload(self):
        """Очистка при выгрузке кога"""
        if self.session:
            asyncio.create_task(self.session.close())

    # Обработчик ошибок для команд
    @setup_telegram_bridge.error
    @telegram_bridge_status.error
    @enable_telegram_bridge.error
    @disable_telegram_bridge.error
    @send_to_telegram.error
    @get_telegram_updates.error
    @set_discord_channel.error
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