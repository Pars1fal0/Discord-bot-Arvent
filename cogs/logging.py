import discord
from discord.ext import commands
import datetime
import json
import os
from typing import Optional


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "logging_config.json"
        self.load_config()

    def load_config(self):
        """Загружает конфигурацию логирования"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {}
            self.save_config()

    def save_config(self):
        """Сохраняет конфигурацию"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get_guild_config(self, guild_id):
        """Получает конфигурацию для сервера"""
        return self.config.get(str(guild_id), {
            "log_channel": None,
            "enabled_events": {
                "message_delete": True,
                "message_edit": True,
                "member_join": True,
                "member_leave": True,
                "member_ban": True,
                "member_unban": True,
                "member_update": True,
                "role_changes": True,
                "channel_changes": True,
                "voice_changes": True
            }
        })

    def set_guild_config(self, guild_id, key, value):
        """Устанавливает настройку для сервера"""
        guild_id = str(guild_id)
        if guild_id not in self.config:
            self.config[guild_id] = self.get_guild_config(guild_id)
        self.config[guild_id][key] = value
        self.save_config()

    async def get_log_channel(self, guild):
        """Получает канал для логов"""
        guild_config = self.get_guild_config(guild.id)
        channel_id = guild_config.get("log_channel")

        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                return channel

        # Ищем канал с названием "логи" или "logs"
        log_channel = discord.utils.get(guild.text_channels, name="логи")
        if not log_channel:
            log_channel = discord.utils.get(guild.text_channels, name="logs")
        if not log_channel:
            log_channel = discord.utils.get(guild.text_channels, name="mod-log")

        return log_channel

    async def send_log(self, guild, embed, event_type):
        """Отправляет лог в канал если событие включено"""
        guild_config = self.get_guild_config(guild.id)

        # Проверяем включено ли логирование этого события
        if not guild_config["enabled_events"].get(event_type, True):
            return

        log_channel = await self.get_log_channel(guild)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except:
                pass  # Если нет прав для отправки

    # ===== СООБЩЕНИЯ =====
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Логирование удаления сообщений"""
        if message.author.bot or not message.guild:
            return

        embed = discord.Embed(
            title="🗑️ Сообщение удалено",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Автор", value=message.author.mention, inline=True)
        embed.add_field(name="Канал", value=message.channel.mention, inline=True)

        if message.content:
            content = message.content[:1024] + "..." if len(message.content) > 1024 else message.content
            embed.add_field(name="Содержимое", value=content, inline=False)

        if message.attachments:
            embed.add_field(name="Вложения", value=f"{len(message.attachments)} файлов", inline=True)

        embed.set_footer(text=f"ID: {message.id}")
        embed.set_thumbnail(
            url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)

        await self.send_log(message.guild, embed, "message_delete")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Логирование редактирования сообщений"""
        if before.author.bot or not before.guild or before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Сообщение отредактировано",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Автор", value=before.author.mention, inline=True)
        embed.add_field(name="Канал", value=before.channel.mention, inline=True)
        embed.add_field(name="Ссылка", value=f"[Перейти]({after.jump_url})", inline=True)

        old_content = before.content[:500] + "..." if len(before.content) > 500 else before.content
        new_content = after.content[:500] + "..." if len(after.content) > 500 else after.content

        embed.add_field(name="Было", value=old_content or "*пусто*", inline=False)
        embed.add_field(name="Стало", value=new_content or "*пусто*", inline=False)

        embed.set_footer(text=f"ID: {before.id}")
        embed.set_thumbnail(url=before.author.avatar.url if before.author.avatar else before.author.default_avatar.url)

        await self.send_log(before.guild, embed, "message_edit")

    # ===== УЧАСТНИКИ =====
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Логирование входа участника"""
        embed = discord.Embed(
            title="✅ Участник присоединился",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Участник", value=f"{member.mention}\n{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="Аккаунт создан", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Участников", value=member.guild.member_count, inline=True)

        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")

        await self.send_log(member.guild, embed, "member_join")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Логирование выхода участника"""
        embed = discord.Embed(
            title="🚪 Участник вышел",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Участник", value=f"{member.display_name}\n{member.name}#{member.discriminator}",
                        inline=True)
        embed.add_field(name="Присоединился", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Участников", value=member.guild.member_count, inline=True)

        roles = [role.mention for role in member.roles[1:]]  # Исключаем @everyone
        if roles:
            roles_text = ", ".join(roles[:5])
            if len(roles) > 5:
                roles_text += f" и ещё {len(roles) - 5}"
            embed.add_field(name="Роли", value=roles_text, inline=False)

        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")

        await self.send_log(member.guild, embed, "member_leave")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Логирование бана"""
        embed = discord.Embed(
            title="🔨 Участник забанен",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Участник", value=f"{user.name}#{user.discriminator}", inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)

        # Пытаемся получить информацию о бане
        try:
            ban = await guild.fetch_ban(user)
            if ban.reason:
                embed.add_field(name="Причина", value=ban.reason, inline=False)
        except:
            pass

        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

        await self.send_log(guild, embed, "member_ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        """Логирование разбана"""
        embed = discord.Embed(
            title="🔓 Участник разбанен",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Участник", value=f"{user.name}#{user.discriminator}", inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)

        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

        await self.send_log(guild, embed, "member_unban")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Логирование изменений участника"""
        # Смена ника
        if before.display_name != after.display_name:
            embed = discord.Embed(
                title="👤 Смена ника",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Участник", value=after.mention, inline=True)
            embed.add_field(name="Было", value=before.display_name, inline=True)
            embed.add_field(name="Стало", value=after.display_name, inline=True)
            embed.set_thumbnail(url=after.avatar.url if after.avatar else after.default_avatar.url)
            await self.send_log(after.guild, embed, "member_update")

        # Смена ролей
        if before.roles != after.roles:
            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]

            if added_roles or removed_roles:
                embed = discord.Embed(
                    title="🎭 Изменение ролей",
                    color=discord.Color.purple(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="Участник", value=after.mention, inline=True)

                if added_roles:
                    embed.add_field(name="Добавлены", value=", ".join([role.mention for role in added_roles]),
                                    inline=False)
                if removed_roles:
                    embed.add_field(name="Удалены", value=", ".join([role.mention for role in removed_roles]),
                                    inline=False)

                embed.set_thumbnail(url=after.avatar.url if after.avatar else after.default_avatar.url)
                await self.send_log(after.guild, embed, "role_changes")

    # ===== КАНАЛЫ =====
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Логирование создания канала"""
        embed = discord.Embed(
            title="📁 Канал создан",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )

        channel_type = "Голосовой" if isinstance(channel, discord.VoiceChannel) else "Текстовый"
        embed.add_field(name="Тип", value=channel_type, inline=True)
        embed.add_field(name="Название", value=channel.name, inline=True)
        embed.add_field(name="Категория", value=channel.category.name if channel.category else "Нет", inline=True)

        await self.send_log(channel.guild, embed, "channel_changes")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Логирование удаления канала"""
        embed = discord.Embed(
            title="🗑️ Канал удалён",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        channel_type = "Голосовой" if isinstance(channel, discord.VoiceChannel) else "Текстовый"
        embed.add_field(name="Тип", value=channel_type, inline=True)
        embed.add_field(name="Название", value=channel.name, inline=True)
        embed.add_field(name="Категория", value=channel.category.name if channel.category else "Нет", inline=True)

        await self.send_log(channel.guild, embed, "channel_changes")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        """Логирование изменений канала"""
        changes = []

        if before.name != after.name:
            changes.append(f"**Название:** {before.name} → {after.name}")

        if before.category != after.category:
            before_cat = before.category.name if before.category else "Нет"
            after_cat = after.category.name if after.category else "Нет"
            changes.append(f"**Категория:** {before_cat} → {after_cat}")

        if changes:
            embed = discord.Embed(
                title="⚙️ Канал изменён",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )

            channel_type = "Голосовой" if isinstance(after, discord.VoiceChannel) else "Текстовый"
            embed.add_field(name="Тип", value=channel_type, inline=True)
            embed.add_field(name="Канал", value=after.mention, inline=True)
            embed.add_field(name="Изменения", value="\n".join(changes), inline=False)

            await self.send_log(after.guild, embed, "channel_changes")

    # ===== ГОЛОСОВЫЕ КАНАЛЫ =====
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Логирование изменений голосового статуса"""
        # Вход в голосовой канал
        if not before.channel and after.channel:
            embed = discord.Embed(
                title="🎤 Вход в голосовой канал",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Канал", value=after.channel.name, inline=True)
            await self.send_log(member.guild, embed, "voice_changes")

        # Выход из голосового канала
        elif before.channel and not after.channel:
            embed = discord.Embed(
                title="🚪 Выход из голосового канала",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Канал", value=before.channel.name, inline=True)
            await self.send_log(member.guild, embed, "voice_changes")

        # Смена голосового канала
        elif before.channel and after.channel and before.channel != after.channel:
            embed = discord.Embed(
                title="🔄 Смена голосового канала",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Было", value=before.channel.name, inline=True)
            embed.add_field(name="Стало", value=after.channel.name, inline=True)
            await self.send_log(member.guild, embed, "voice_changes")

        # Мьют/дефьют
        elif before.self_mute != after.self_mute:
            status = "🔇 Самомьют" if after.self_mute else "🔊 Снятие самомьюта"
            embed = discord.Embed(
                title=status,
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Канал", value=after.channel.name if after.channel else "Неизвестно", inline=True)
            await self.send_log(member.guild, embed, "voice_changes")

    # ===== КОМАНДЫ НАСТРОЙКИ =====
    @commands.group()
    @commands.has_permissions(administrator=True)
    async def logs(self, ctx):
        """Управление системой логов"""
        if ctx.invoked_subcommand is None:
            await self.show_logs_settings(ctx)

    @logs.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Установить канал для логов"""
        self.set_guild_config(ctx.guild.id, "log_channel", channel.id)

        embed = discord.Embed(
            title="✅ Канал логов установлен",
            description=f"Логи будут отправляться в {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @logs.command()
    async def enable(self, ctx, event_type: str):
        """Включить логирование определенного события"""
        guild_config = self.get_guild_config(ctx.guild.id)

        if event_type in guild_config["enabled_events"]:
            guild_config["enabled_events"][event_type] = True
            self.set_guild_config(ctx.guild.id, "enabled_events", guild_config["enabled_events"])

            embed = discord.Embed(
                title="✅ Событие включено",
                description=f"Логирование `{event_type}` включено",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Неизвестное событие",
                color=discord.Color.red()
            )

        await ctx.send(embed=embed)

    @logs.command()
    async def disable(self, ctx, event_type: str):
        """Выключить логирование определенного события"""
        guild_config = self.get_guild_config(ctx.guild.id)

        if event_type in guild_config["enabled_events"]:
            guild_config["enabled_events"][event_type] = False
            self.set_guild_config(ctx.guild.id, "enabled_events", guild_config["enabled_events"])

            embed = discord.Embed(
                title="✅ Событие выключено",
                description=f"Логирование `{event_type}` выключено",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="❌ Неизвестное событие",
                color=discord.Color.red()
            )

        await ctx.send(embed=embed)

    @logs.command()
    async def settings(self, ctx):
        """Показать текущие настройки логов"""
        await self.show_logs_settings(ctx)

    async def show_logs_settings(self, ctx):
        """Показать настройки логов"""
        guild_config = self.get_guild_config(ctx.guild.id)
        log_channel = ctx.guild.get_channel(guild_config.get("log_channel"))

        embed = discord.Embed(
            title="⚙️ Настройки системы логов",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="📝 Канал логов",
            value=log_channel.mention if log_channel else "❌ Не установлен",
            inline=False
        )

        # Статус событий
        enabled_events = []
        disabled_events = []

        for event, enabled in guild_config["enabled_events"].items():
            if enabled:
                enabled_events.append(f"✅ {event}")
            else:
                disabled_events.append(f"❌ {event}")

        if enabled_events:
            embed.add_field(
                name="🟢 Включенные события",
                value="\n".join(enabled_events[:8]),
                inline=True
            )

        if disabled_events:
            embed.add_field(
                name="🔴 Выключенные события",
                value="\n".join(disabled_events[:8]),
                inline=True
            )

        embed.add_field(
            name="📋 Команды",
            value=(
                "`!logs channel #канал` - установить канал\n"
                "`!logs enable событие` - включить событие\n"
                "`!logs disable событие` - выключить событие\n"
                "`!logs settings` - показать настройки"
            ),
            inline=False
        )

        await ctx.send(embed=embed)

    @logs.command()
    async def test(self, ctx):
        """Тестовая отправка лога"""
        embed = discord.Embed(
            title="🧪 Тестовое лог-сообщение",
            description="Если вы видите это сообщение, система логов работает корректно!",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Канал", value=ctx.channel.mention, inline=True)
        embed.add_field(name="Участник", value=ctx.author.mention, inline=True)

        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)
            await ctx.send("✅ Тестовое сообщение отправлено в канал логов!")
        else:
            await ctx.send("❌ Канал логов не найден! Установите его командой `!logs channel #канал`")


async def setup(bot):
    await bot.add_cog(Logging(bot))