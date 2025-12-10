import re
import json
import datetime
from collections import defaultdict, deque
from urllib.parse import urlparse
import asyncio
import typing as t

import discord
from discord import app_commands
from discord.ext import commands

WARNINGS_FILE = "warnings.json"
CONFIG_FILE = "moderation_config.json"
MUTES_FILE = "mutes.json"  # файл для хранения временных мьютов

# Дефолтные списки доменов (для новых серверов)
DEFAULT_ALLOWED_DOMAINS = {
    "discord.com",
    "discord.gg",
    "media.discordapp.net",
    "tenor.com",
    "youtube.com",
    "youtu.be",
}

DEFAULT_BLOCKED_DOMAINS = {
    "t.me",
    "telegraph.ph",
    "vk.com",
    "ok.ru",
}

# Антикапс / антифлуд
CAPS_MIN_LENGTH = 10
CAPS_PERCENT = 0.7

SPAM_WINDOW = 5  # окно для антифлуда (сек)
SPAM_THRESHOLD = 5  # сколько сообщений за SPAM_WINDOW считается флудом

FLOOD_MUTE_MINUTES = 5  # мут при флуде (в минутах)

# Наказания по количеству предупреждений
# Пример: при 3 варнах → авто-мьют
PUNISHMENTS = {
    3: "mute"
}
MAX_WARNINGS = max(PUNISHMENTS.keys())
AUTO_MUTE_MINUTES = 10  # длительность авто-мьюта по варну (из PUNISHMENTS)

URL_REGEX = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)


class Moder(commands.Cog):
    """
    Модерация:
    - анти-капс / анти-флуд / фильтр ссылок
    - система предупреждений (с наказаниями по PUNISHMENTS)
    - лог-канал
    - настраиваемые списки доменов
    - ручные мьюты: /mute / /unmute / /tempmute / /muted_list / /muteinfo
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = self.load_warnings()
        self.config = self.load_config()
        self.mutes = self.load_mutes()  # {guild_id(str): {user_id(str): unmute_ts(float)}}
        # user_messages[guild_id][user_id] = deque[timestamps]
        self.user_messages: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(deque))
        self.last_flood: dict[int, dict[int, float]] = defaultdict(dict)
        self._mute_task: t.Optional[asyncio.Task] = None

    async def cog_load(self):
        """Запускаем фонового смотрителя мьютов при загрузке кога."""
        self._mute_task = self.bot.loop.create_task(self.mute_watcher())

    async def cog_unload(self):
        if self._mute_task:
            self._mute_task.cancel()

    # ===== Файлы предупреждений / конфиг / мьюты =====

    def load_warnings(self) -> dict:
        try:
            with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_warnings(self) -> None:
        with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.warnings, f, ensure_ascii=False, indent=4)

    def load_config(self) -> dict:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_config(self) -> None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def load_mutes(self) -> dict:
        """Загружаем активные ВРЕМЕННЫЕ мьюты из файла."""
        try:
            with open(MUTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_mutes(self) -> None:
        with open(MUTES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.mutes, f, ensure_ascii=False, indent=4)

    def get_guild_config(self, guild: discord.Guild) -> dict:
        """Конфиг для сервера, с дефолтами если ещё нет."""
        gid = str(guild.id)
        if gid not in self.config:
            self.config[gid] = {
                "log_channel_id": None,
                "allowed_domains": list(DEFAULT_ALLOWED_DOMAINS),
                "blocked_domains": list(DEFAULT_BLOCKED_DOMAINS),
            }
            self.save_config()
        else:
            cfg = self.config[gid]
            if "allowed_domains" not in cfg:
                cfg["allowed_domains"] = list(DEFAULT_ALLOWED_DOMAINS)
            if "blocked_domains" not in cfg:
                cfg["blocked_domains"] = list(DEFAULT_BLOCKED_DOMAINS)
            if "log_channel_id" not in cfg:
                cfg["log_channel_id"] = None
        return self.config[gid]

    # ===== Предупреждения =====

    def get_warn_count(self, guild_id: int, user_id: int) -> int:
        return self.warnings.get(str(guild_id), {}).get(str(user_id), 0)

    def add_warning(self, guild_id: int, user_id: int) -> int:
        gid = str(guild_id)
        uid = str(user_id)
        if gid not in self.warnings:
            self.warnings[gid] = {}
        self.warnings[gid][uid] = self.warnings[gid].get(uid, 0) + 1
        self.save_warnings()
        return self.warnings[gid][uid]

    def clear_warnings(self, guild_id: int, user_id: int) -> None:
        gid = str(guild_id)
        uid = str(user_id)
        if gid in self.warnings and uid in self.warnings[gid]:
            del self.warnings[gid][uid]
            self.save_warnings()

    # ===== Антикапс / антифлуд =====

    def is_caps_abuse(self, content: str) -> bool:
        letters = [c for c in content if c.isalpha()]
        if len(letters) < CAPS_MIN_LENGTH:
            return False
        upper_count = sum(1 for c in letters if c.isupper())
        return (upper_count / len(letters)) >= CAPS_PERCENT

    def check_flood(self, message: discord.Message) -> bool:
        """True, если пользователь флудит (SPAM_THRESHOLD сообщений за SPAM_WINDOW сек)."""
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        guild_id = message.guild.id
        user_id = message.author.id

        dq = self.user_messages[guild_id][user_id]
        dq.append(now)

        # чистим окно
        while dq and now - dq[0] > SPAM_WINDOW:
            dq.popleft()

        return len(dq) >= SPAM_THRESHOLD

    # ===== Домены и ссылки =====

    def extract_domains(self, text: str, blocked_domains: set[str]) -> set[str]:
        """Парсим домены из текста + 'голые' заблокированные."""
        domains: set[str] = set()

        # http(s)-ссылки
        for match in URL_REGEX.findall(text):
            try:
                parsed = urlparse(match)
                host = parsed.hostname
                if host:
                    host = host.lower()
                    if host.startswith("www."):
                        host = host[4:]
                    domains.add(host)
            except ValueError:
                continue

        # голые домены из блок-листа
        low = text.lower()
        for d in blocked_domains:
            if d in low:
                domains.add(d)

        return domains

    def has_blocked_link(self, text: str, guild: discord.Guild) -> tuple[bool, list[str]]:
        """Проверка на запрещённые/неразрешённые домены для этого сервера."""
        cfg = self.get_guild_config(guild)
        allowed = set(cfg.get("allowed_domains", []))
        blocked = set(cfg.get("blocked_domains", []))

        domains = self.extract_domains(text, blocked)
        if not domains:
            return False, []

        blocked_domains: set[str] = set()
        for domain in domains:
            # 1) явно заблокированный
            for bad in blocked:
                if domain == bad or domain.endswith("." + bad):
                    blocked_domains.add(domain)
                    break
            else:
                # 2) если есть allow-лист и домен не в нём — блочим
                if allowed and not any(domain == good or domain.endswith("." + good) for good in allowed):
                    blocked_domains.add(domain)

        return (len(blocked_domains) > 0), sorted(blocked_domains)

    # ===== Логи =====

    def get_log_channel(self, guild: discord.Guild):
        cfg = self.get_guild_config(guild)
        log_id = cfg.get("log_channel_id")
        if not log_id:
            return None
        channel = guild.get_channel(log_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def log_action(
            self,
            guild: discord.Guild,
            *,
            member: t.Optional[discord.Member] = None,
            action: str,
            reason: t.Optional[str] = None,
            moderator: t.Any = None,
            message: t.Optional[discord.Message] = None,
            extra: t.Optional[str] = None,
    ):
        channel = self.get_log_channel(guild)
        if channel is None:
            return

        embed = discord.Embed(
            title=f"Модерация: {action}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        if member:
            embed.add_field(
                name="Пользователь",
                value=f"{member.mention} (`{member.id}`)",
                inline=False
            )

        if moderator:
            if isinstance(moderator, discord.Member):
                mod_val = f"{moderator.mention} (`{moderator.id}`)"
            else:
                mod_val = str(moderator)
            embed.add_field(name="Модератор", value=mod_val, inline=False)

        if reason:
            embed.add_field(name="Причина", value=reason, inline=False)

        if message:
            content = message.content
            if len(content) > 1024:
                content = content[:1000] + "...(+)"
            embed.add_field(name="Сообщение", value=content or "*без текста*", inline=False)
            embed.add_field(name="Канал", value=message.channel.mention, inline=True)
            embed.add_field(name="Ссылка", value=message.jump_url, inline=True)

        if extra:
            embed.add_field(name="Дополнительно", value=extra, inline=False)

        await channel.send(embed=embed)

    # ===== Роль Muted и система мьютов =====

    async def create_mute_role(self, guild: discord.Guild):
        """Создаёт/находит роль Muted и настраивает права во всех каналах."""
        mute_role = discord.utils.get(guild.roles, name="Muted")

        if not mute_role:
            try:
                mute_role = await guild.create_role(
                    name="Muted",
                    color=discord.Color.dark_gray(),
                    reason="Роль для мьюта пользователей"
                )

                for channel in guild.channels:
                    try:
                        await channel.set_permissions(
                            mute_role,
                            send_messages=False,
                            send_messages_in_threads=False,
                            create_public_threads=False,
                            create_private_threads=False,
                            speak=False,
                            add_reactions=False,
                            connect=False
                        )
                    except Exception:
                        continue

            except discord.Forbidden:
                return None

        return mute_role

    async def mute_watcher(self):
        """Периодически проверяет, у кого истёк мут, и снимает роль Muted (даже после перезапуска)."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = datetime.datetime.now(datetime.timezone.utc).timestamp()
            changed = False

            for gid, users in list(self.mutes.items()):
                guild = self.bot.get_guild(int(gid))
                if not guild:
                    continue

                for uid, ts in list(users.items()):
                    if ts <= now:
                        member = guild.get_member(int(uid))
                        mute_role = discord.utils.get(guild.roles, name="Muted")
                        if member and mute_role and mute_role in member.roles:
                            try:
                                await member.remove_roles(mute_role, reason="Авто-размьют (по времени)")
                            except Exception:
                                pass
                        del users[uid]
                        changed = True

                if not users:
                    del self.mutes[gid]

            if changed:
                self.save_mutes()

            await asyncio.sleep(5)

    def register_mute(self, member: discord.Member, unmute_time: datetime.datetime):
        """Записываем ВРЕМЕННЫЙ мьют в self.mutes + сохраняем в файл."""
        gid = str(member.guild.id)
        uid = str(member.id)
        if gid not in self.mutes:
            self.mutes[gid] = {}
        self.mutes[gid][uid] = float(unmute_time.timestamp())
        self.save_mutes()

    def remove_mute_record(self, guild_id: int, user_id: int):
        gid = str(guild_id)
        uid = str(user_id)
        if gid in self.mutes and uid in self.mutes[gid]:
            del self.mutes[gid][uid]
            if not self.mutes[gid]:
                del self.mutes[gid]
            self.save_mutes()

    # ===== Наказания по варнам (mute по PUNISHMENTS) =====

    async def apply_punishment(
            self,
            member: discord.Member,
            warn_count: int,
            base_reason: str,
            source_channel: discord.abc.Messageable,
            auto: bool = True,
    ):
        guild = member.guild
        action = PUNISHMENTS.get(warn_count)
        if not action:
            return

        if action == "mute":
            mute_role = await self.create_mute_role(guild)
            if not mute_role:
                await source_channel.send("❌ Не удалось создать или найти роль для мьюта!")
                return

            if mute_role in member.roles:
                await source_channel.send(f"ℹ️ {member.mention} уже замьючен(а).")
                return

            duration_sec = AUTO_MUTE_MINUTES * 60
            unmute_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration_sec)

            try:
                await member.add_roles(mute_role, reason=base_reason)
            except discord.Forbidden:
                await source_channel.send("❌ У меня нет прав для выдачи роли Muted!")
                return
            except discord.HTTPException:
                await source_channel.send("❌ Не удалось выдать роль Muted по технической причине.")
                return

            await source_channel.send(
                f"🔇 {member.mention} получил(а) мут на **{AUTO_MUTE_MINUTES} мин.** "
                f"(варн {warn_count}/{MAX_WARNINGS})."
            )

            await self.log_action(
                guild,
                member=member,
                action="Авто-мут" if auto else "Мут",
                reason=f"{base_reason} | {AUTO_MUTE_MINUTES} минут",
                moderator="AutoMod" if auto else None,
            )

            # DM пользователю
            try:
                unmute_ts = int(unmute_time.timestamp())
                dm_embed = discord.Embed(
                    title="⏰ Вы были временно замьючены",
                    description=f"На сервере **{guild.name}**",
                    color=discord.Color.orange()
                )
                dm_embed.add_field(name="Длительность", value=f"{AUTO_MUTE_MINUTES} мин.", inline=True)
                dm_embed.add_field(name="Причина", value=base_reason, inline=False)
                dm_embed.add_field(name="Размут", value=f"<t:{unmute_ts}:R>", inline=True)
                await member.send(embed=dm_embed)
            except Exception:
                pass

            # записываем мьют в файл (временный)
            self.register_mute(member, unmute_time)

        # после достижения максимума варнов — сбрасываем
        if warn_count >= MAX_WARNINGS:
            self.clear_warnings(guild.id, member.id)

    async def auto_warn(self, message: discord.Message, reason: str):
        """
        Общий авто-варн (капс/ссылки и т.п.) + проверка PUNISHMENTS.
        Для флуда отдельная логика, чтобы не спамить варнами.
        """
        member = message.author
        guild = message.guild
        channel = message.channel

        warn_count = self.add_warning(guild.id, member.id)

        # предупреждение только в ЛС пользователю
        dm_text = (
            f"⚠️ Ты получил предупреждение на сервере **{guild.name}** "
            f"за **{reason}** (**{warn_count}/{MAX_WARNINGS}**)."
        )
        try:
            await member.send(dm_text)
        except discord.Forbidden:
            pass

        await self.log_action(
            guild,
            member=member,
            action="Авто-предупреждение",
            reason=reason,
            moderator="AutoMod",
            message=message,
            extra=f"Всего предупреждений: {warn_count}/{MAX_WARNINGS}",
        )

        await self.apply_punishment(member, warn_count, reason, channel, auto=True)

    # ===== Специальная обработка флуда: 1 варн + мут 5 мин за всплеск =====

    async def handle_flood_violation(self, message: discord.Message):
        """Даём ОДНО предупреждение за флуд + мьют на FLOOD_MUTE_MINUTES."""
        member = message.author
        guild = message.guild
        channel = message.channel

        reason = "флуд (слишком много сообщений за короткое время)"
        warn_count = self.add_warning(guild.id, member.id)

        # ЛС пользователю
        dm_text = (
            f"⚠️ Ты получил предупреждение на сервере **{guild.name}** "
            f"за **{reason}** (**{warn_count}/{MAX_WARNINGS}**)."
        )
        try:
            await member.send(dm_text)
        except discord.Forbidden:
            pass

        await self.log_action(
            guild,
            member=member,
            action="Авто-предупреждение (флуд)",
            reason=reason,
            moderator="AutoMod",
            message=message,
            extra=f"Всего предупреждений: {warn_count}/{MAX_WARNINGS}",
        )

        # мут на FLOOD_MUTE_MINUTES
        mute_role = await self.create_mute_role(guild)
        if not mute_role:
            await channel.send("❌ Не удалось создать или найти роль для мьюта!")
            return

        if mute_role in member.roles:
            return  # уже замьючен, не дублируем

        duration_sec = FLOOD_MUTE_MINUTES * 60
        unmute_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration_sec)

        try:
            await member.add_roles(mute_role, reason=reason)
        except discord.Forbidden:
            await channel.send("❌ У меня нет прав для выдачи роли Muted!")
            return
        except discord.HTTPException:
            await channel.send("❌ Не удалось выдать роль Muted по технической причине.")
            return

        await channel.send(
            f"🔇 {member.mention} замьючен на **{FLOOD_MUTE_MINUTES} мин.** за флуд."
        )

        await self.log_action(
            guild,
            member=member,
            action="Авто-мут (флуд)",
            reason=f"{reason} | {FLOOD_MUTE_MINUTES} минут",
            moderator="AutoMod",
        )

        # DM про мьют
        try:
            unmute_ts = int(unmute_time.timestamp())
            dm_embed = discord.Embed(
                title="⏰ Вы были временно замьючены",
                description=f"На сервере **{guild.name}**",
                color=discord.Color.orange()
            )
            dm_embed.add_field(name="Длительность", value=f"{FLOOD_MUTE_MINUTES} мин.", inline=True)
            dm_embed.add_field(name="Причина", value=reason, inline=False)
            dm_embed.add_field(name="Размут", value=f"<t:{unmute_ts}:R>", inline=True)
            await member.send(embed=dm_embed)
        except Exception:
            pass

        # записываем мьют в файл
        self.register_mute(member, unmute_time)

        # при достижении MAX_WARNINGS — чистим варны
        if warn_count >= MAX_WARNINGS:
            self.clear_warnings(guild.id, member.id)

    # ===== Автомод сообщений =====

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # игнор ботов / ЛС
        if message.author.bot or message.guild is None:
            return

        # модераторов с manage_messages не трогаем
        if message.author.guild_permissions.manage_messages:
            return

        content = message.content

        # игнорируем команды
        if content.startswith(("!", "/", ".", "?", "-")):
            return

        # 1) ссылки
        blocked, domains = self.has_blocked_link(content, message.guild)
        if blocked:
            try:
                await message.delete()
            except discord.Forbidden:
                pass

            domains_str = ", ".join(domains)
            reason = f"запрещённые или неразрешённые ссылки ({domains_str})"
            await self.auto_warn(message, reason)
            return

        # 2) капс
        if self.is_caps_abuse(content):
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await self.auto_warn(message, "злоупотребление КАПСОМ")
            return

        # 3) флуд
        if self.check_flood(message):
            now = datetime.datetime.now(datetime.timezone.utc).timestamp()
            guild_id = message.guild.id
            user_id = message.author.id

            last = self.last_flood[guild_id].get(user_id, 0.0)

            # если уже наказывали за флуд в ближайшие SPAM_WINDOW сек —
            # просто удаляем сообщение без доп. варнов/мьютов
            if now - last < SPAM_WINDOW:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                return

            # Обновляем время последнего флуда и наказываем 1 раз
            self.last_flood[guild_id][user_id] = now

            try:
                await message.delete()
            except discord.Forbidden:
                pass

            await self.handle_flood_violation(message)
            return

    # ===== СЛЭШ-КОМАНДЫ ПРЕДУПРЕЖДЕНИЙ =====

    @app_commands.command(name="warn", description="Выдать предупреждение пользователю")
    @app_commands.describe(
        member="Пользователь для выдачи предупреждения",
        reason="Причина предупреждения"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def warn_command(self, interaction: discord.Interaction, member: discord.Member,
                           reason: str = "Нарушение правил"):
        """Выдать варн вручную (и автоматически наказать по PUNISHMENTS)."""
        await interaction.response.defer(ephemeral=True)

        warn_count = self.add_warning(interaction.guild.id, member.id)

        # ЛС пользователю
        dm_text = (
            f"⚠️ Ты получил предупреждение на сервере **{interaction.guild.name}** "
            f"за **{reason}** (**{warn_count}/{MAX_WARNINGS}**)."
        )
        try:
            await member.send(dm_text)
        except discord.Forbidden:
            pass

        # Краткое подтверждение в канал для модератора
        await interaction.followup.send(
            f"✅ Предупреждение выдано пользователю {member.mention} "
            f"(**{warn_count}/{MAX_WARNINGS}**)."
        )

        await self.log_action(
            interaction.guild,
            member=member,
            action="Предупреждение",
            reason=reason,
            moderator=interaction.user,
            extra=f"Всего предупреждений: {warn_count}/{MAX_WARNINGS}",
        )

        await self.apply_punishment(member, warn_count, reason, interaction.channel, auto=False)

    @app_commands.command(name="unwarn", description="Сбросить все предупреждения пользователя")
    @app_commands.describe(member="Пользователь для сброса предупреждений")
    @app_commands.default_permissions(manage_messages=True)
    async def unwarn_command(self, interaction: discord.Interaction, member: discord.Member):
        """Сбросить все варны у пользователя."""
        await interaction.response.defer(ephemeral=True)

        self.clear_warnings(interaction.guild.id, member.id)
        await interaction.followup.send(f"✅ Все предупреждения с {member.mention} сняты.")

        await self.log_action(
            interaction.guild,
            member=member,
            action="Снятие предупреждений",
            reason="Сброс варнов командой unwarn",
            moderator=interaction.user,
        )

    @app_commands.command(name="warnings", description="Посмотреть количество предупреждений")
    @app_commands.describe(member="Пользователь для проверки (по умолчанию - вы)")
    @app_commands.default_permissions(manage_messages=True)
    async def warnings_command(self, interaction: discord.Interaction, member: discord.Member = None):
        """Посмотреть кол-во варнов."""
        await interaction.response.defer(ephemeral=True)

        member = member or interaction.user
        count = self.get_warn_count(interaction.guild.id, member.id)
        await interaction.followup.send(f"ℹ️ У {member.mention} сейчас **{count}** предупреждений (из {MAX_WARNINGS}).")

    # ===== СЛЭШ-КОМАНДЫ МЬЮТОВ =====

    @app_commands.command(name="mute", description="Замутить пользователя бессрочно")
    @app_commands.describe(
        member="Пользователь для мьюта",
        reason="Причина мьюта"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def manual_mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
        """Замутить пользователя бессрочно (ручная команда)."""
        await interaction.response.defer()

        if member == interaction.user:
            await interaction.followup.send("❌ Нельзя замутить самого себя!", ephemeral=True)
            return

        if member.guild_permissions.administrator:
            await interaction.followup.send("❌ Нельзя замутить администратора!", ephemeral=True)
            return

        mute_role = await self.create_mute_role(interaction.guild)
        if not mute_role:
            await interaction.followup.send("❌ Не удалось создать или найти роль для мьюта!", ephemeral=True)
            return

        if mute_role in member.roles:
            await interaction.followup.send("❌ Этот пользователь уже замьючен!", ephemeral=True)
            return

        try:
            await member.add_roles(mute_role, reason=reason)

            embed = discord.Embed(
                title="🔇 Пользователь замьючен",
                color=discord.Color.red()
            )
            embed.add_field(name="Пользователь", value=member.mention, inline=True)
            embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

            await interaction.followup.send(embed=embed)

            # ЛС пользователю
            try:
                dm_embed = discord.Embed(
                    title="🔇 Вы были замьючены",
                    description=f"На сервере **{interaction.guild.name}**",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Модератор", value=interaction.user.display_name, inline=True)
                dm_embed.add_field(name="Причина", value=reason, inline=True)
                await member.send(embed=dm_embed)
            except Exception:
                pass

            # лог
            await self.log_action(
                interaction.guild,
                member=member,
                action="Мьют (ручной)",
                reason=reason,
                moderator=interaction.user,
            )

        except discord.Forbidden:
            await interaction.followup.send("❌ У меня нет прав для выдачи ролей!", ephemeral=True)

    @app_commands.command(name="unmute", description="Размутить пользователя")
    @app_commands.describe(
        member="Пользователь для размьюта",
        reason="Причина размьюта"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def manual_unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
        """Размутить пользователя."""
        await interaction.response.defer()

        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")

        if not mute_role:
            await interaction.followup.send("❌ Роль для мьюта не найдена!", ephemeral=True)
            return

        if mute_role not in member.roles:
            await interaction.followup.send("❌ Этот пользователь не замьючен!", ephemeral=True)
            return

        try:
            await member.remove_roles(mute_role, reason=reason)

            # удаляем запись о временном мьюте, если была
            self.remove_mute_record(interaction.guild.id, member.id)

            embed = discord.Embed(
                title="🔊 Пользователь размьючен",
                color=discord.Color.green()
            )
            embed.add_field(name="Пользователь", value=member.mention, inline=True)
            embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

            await interaction.followup.send(embed=embed)

            # ЛС пользователю
            try:
                dm_embed = discord.Embed(
                    title="🔊 Вы были размьючены",
                    description=f"На сервере **{interaction.guild.name}**",
                    color=discord.Color.green()
                )
                dm_embed.add_field(name="Модератор", value=interaction.user.display_name, inline=True)
                dm_embed.add_field(name="Причина", value=reason, inline=True)
                await member.send(embed=dm_embed)
            except Exception:
                pass

            await self.log_action(
                interaction.guild,
                member=member,
                action="Размьют (ручной)",
                reason=reason,
                moderator=interaction.user,
            )

        except discord.Forbidden:
            await interaction.followup.send("❌ У меня нет прав для управления ролями!", ephemeral=True)

    @app_commands.command(name="tempmute", description="Временно замутить пользователя")
    @app_commands.describe(
        member="Пользователь для временного мьюта",
        duration="Длительность мьюта (10s, 5m, 1h, 1d)",
        reason="Причина мьюта"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def manual_tempmute(self, interaction: discord.Interaction, member: discord.Member, duration: str,
                              reason: str = "Не указана"):
        """Временно замутить пользователя (пример: 10s, 5m, 1h, 1d)."""
        await interaction.response.defer()

        if member == interaction.user:
            await interaction.followup.send("❌ Нельзя замутить самого себя!", ephemeral=True)
            return

        if member.guild_permissions.administrator:
            await interaction.followup.send("❌ Нельзя замутить администратора!", ephemeral=True)
            return

        time_units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }

        try:
            unit = duration[-1].lower()
            if unit not in time_units:
                raise ValueError

            amount = int(duration[:-1])
            if amount <= 0:
                raise ValueError

            seconds = amount * time_units[unit]
            unmute_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)

        except (ValueError, IndexError):
            embed = discord.Embed(
                title="❌ Неверный формат времени",
                description="Используйте: `10s` (секунды), `5m` (минуты), `1h` (часы), `1d` (дни)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        mute_role = await self.create_mute_role(interaction.guild)
        if not mute_role:
            await interaction.followup.send("❌ Не удалось создать или найти роль для мьюта!", ephemeral=True)
            return

        if mute_role in member.roles:
            await interaction.followup.send("❌ Этот пользователь уже замьючен!", ephemeral=True)
            return

        try:
            await member.add_roles(mute_role, reason=reason)

            # сохраняем мьют как временный
            self.register_mute(member, unmute_time)

            time_formats = {
                's': f"{amount} секунд",
                'm': f"{amount} минут",
                'h': f"{amount} часов",
                'd': f"{amount} дней"
            }

            unmute_ts = int(unmute_time.timestamp())

            embed = discord.Embed(
                title="⏰ Пользователь временно замьючен",
                color=discord.Color.orange()
            )
            embed.add_field(name="Пользователь", value=member.mention, inline=True)
            embed.add_field(name="Длительность", value=time_formats[unit], inline=True)
            embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            embed.add_field(name="Размут", value=f"<t:{unmute_ts}:R>", inline=True)

            await interaction.followup.send(embed=embed)

            # ЛС пользователю
            try:
                dm_embed = discord.Embed(
                    title="⏰ Вы были временно замьючены",
                    description=f"На сервере **{interaction.guild.name}**",
                    color=discord.Color.orange()
                )
                dm_embed.add_field(name="Длительность", value=time_formats[unit], inline=True)
                dm_embed.add_field(name="Размут", value=f"<t:{unmute_ts}:R>", inline=True)
                dm_embed.add_field(name="Модератор", value=interaction.user.display_name, inline=False)
                dm_embed.add_field(name="Причина", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except Exception:
                pass

            await self.log_action(
                interaction.guild,
                member=member,
                action="Временный мьют (ручной)",
                reason=f"{reason} | {time_formats[unit]}",
                moderator=interaction.user,
            )

        except discord.Forbidden:
            await interaction.followup.send("❌ У меня нет прав для выдачи ролей!", ephemeral=True)

    @app_commands.command(name="muted_list", description="Показать список замьюченных пользователей")
    @app_commands.default_permissions(manage_roles=True)
    async def muted_list(self, interaction: discord.Interaction):
        """Показать список замьюченных пользователей."""
        await interaction.response.defer(ephemeral=True)

        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")

        if not mute_role:
            await interaction.followup.send("❌ Роль для мьюта не найдена!")
            return

        muted_members = [member for member in interaction.guild.members if mute_role in member.roles]

        if not muted_members:
            await interaction.followup.send("🔊 На сервере нет замьюченных пользователей!")
            return

        embed = discord.Embed(
            title="📋 Список замьюченных пользователей",
            color=discord.Color.orange()
        )

        guild_id = str(interaction.guild.id)
        guild_mutes = self.mutes.get(guild_id, {})

        for i, member in enumerate(muted_members[:10], 1):
            uid = str(member.id)
            if uid in guild_mutes:
                unmute_ts = guild_mutes[uid]
                time_info = f"Размут: <t:{int(unmute_ts)}:R>"
            else:
                time_info = "⏳ Бессрочно"

            embed.add_field(
                name=f"{i}. {member.display_name}",
                value=f"{member.mention}\n{time_info}",
                inline=False
            )

        if len(muted_members) > 10:
            embed.set_footer(text=f"И ещё {len(muted_members) - 10} пользователей...")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="muteinfo", description="Информация о мьюте пользователя")
    @app_commands.describe(member="Пользователь для проверки мьюта")
    @app_commands.default_permissions(manage_roles=True)
    async def muteinfo(self, interaction: discord.Interaction, member: discord.Member):
        """Информация о мьюте пользователя."""
        await interaction.response.defer(ephemeral=True)

        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")

        if not mute_role or mute_role not in member.roles:
            await interaction.followup.send("❌ Этот пользователь не замьючен!")
            return

        embed = discord.Embed(
            title=f"ℹ️ Информация о мьюте {member.display_name}",
            color=discord.Color.blue()
        )

        embed.add_field(name="Пользователь", value=member.mention, inline=True)
        embed.add_field(name="Статус", value="🔇 Замьючен", inline=True)

        guild_id = str(interaction.guild.id)
        uid = str(member.id)
        guild_mutes = self.mutes.get(guild_id, {})

        if uid in guild_mutes:
            unmute_ts = guild_mutes[uid]
            embed.add_field(name="Тип мьюта", value="⏰ Временный", inline=True)
            embed.add_field(name="Размут", value=f"<t:{int(unmute_ts)}:R>", inline=True)
            embed.add_field(name="Осталось", value=f"<t:{int(unmute_ts)}:R>", inline=True)
        else:
            embed.add_field(name="Тип мьюта", value="⏳ Бессрочный", inline=True)

        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

        await interaction.followup.send(embed=embed)

    # ===== Восстановление мьюта при заходе =====

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Восстанавливает ВРЕМЕННЫЙ мьют, если пользователь вышел и вернулся до окончания срока."""
        guild_id = str(member.guild.id)
        uid = str(member.id)

        if guild_id in self.mutes and uid in self.mutes[guild_id]:
            unmute_ts = self.mutes[guild_id][uid]
            now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

            if unmute_ts <= now_ts:
                # срок уже истёк — чистим запись
                self.remove_mute_record(member.guild.id, member.id)
                return

            mute_role = await self.create_mute_role(member.guild)
            if mute_role:
                await asyncio.sleep(1)  # немного ждём, пока обновятся роли
                try:
                    await member.add_roles(mute_role, reason="Восстановление временного мьюта при повторном входе")
                except Exception:
                    pass

    # ===== СЛЭШ-КОМАНДЫ НАСТРОЙКИ =====

    @app_commands.command(name="setlog", description="Установить лог-канал для модерации")
    @app_commands.describe(channel="Канал для логов модерации")
    @app_commands.default_permissions(manage_guild=True)
    async def setlog_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Установить лог-канал для модерации."""
        await interaction.response.defer(ephemeral=True)

        cfg = self.get_guild_config(interaction.guild)
        cfg["log_channel_id"] = channel.id
        self.save_config()
        await interaction.followup.send(f"✅ Лог-канал для модерации установлен: {channel.mention}")

    @app_commands.command(name="adddomain", description="Добавить домен в белый список")
    @app_commands.describe(domain="Домен для добавления в разрешенные")
    @app_commands.default_permissions(manage_guild=True)
    async def adddomain_command(self, interaction: discord.Interaction, domain: str):
        """
        Добавить домен в белый список (разрешённые ссылки).
        Пример: /adddomain youtube.com
        """
        await interaction.response.defer(ephemeral=True)

        domain = domain.lower().strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            parsed = urlparse(domain)
            domain = parsed.hostname or domain
        if domain.startswith("www."):
            domain = domain[4:]

        cfg = self.get_guild_config(interaction.guild)
        allowed = set(cfg.get("allowed_domains", []))
        blocked = set(cfg.get("blocked_domains", []))

        if domain in blocked:
            blocked.remove(domain)

        allowed.add(domain)
        cfg["allowed_domains"] = sorted(allowed)
        cfg["blocked_domains"] = sorted(blocked)
        self.save_config()

        await interaction.followup.send(f"✅ Домен `{domain}` добавлен в **разрешённые**.")

    @app_commands.command(name="blockdomain", description="Добавить домен в черный список")
    @app_commands.describe(domain="Домен для добавления в запрещенные")
    @app_commands.default_permissions(manage_guild=True)
    async def blockdomain_command(self, interaction: discord.Interaction, domain: str):
        """
        Добавить домен в чёрный список (запрещённые ссылки).
        Пример: /blockdomain t.me
        """
        await interaction.response.defer(ephemeral=True)

        domain = domain.lower().strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            parsed = urlparse(domain)
            domain = parsed.hostname or domain
        if domain.startswith("www."):
            domain = domain[4:]

        cfg = self.get_guild_config(interaction.guild)
        allowed = set(cfg.get("allowed_domains", []))
        blocked = set(cfg.get("blocked_domains", []))

        if domain in allowed:
            allowed.remove(domain)

        blocked.add(domain)
        cfg["allowed_domains"] = sorted(allowed)
        cfg["blocked_domains"] = sorted(blocked)
        self.save_config()

        await interaction.followup.send(f"✅ Домен `{domain}` добавлен в **запрещённые**.")

    @app_commands.command(name="domains", description="Показать текущие списки доменов и лог-канал")
    @app_commands.default_permissions(manage_guild=True)
    async def domains_command(self, interaction: discord.Interaction):
        """Показать текущие списки доменов и лог-канал."""
        await interaction.response.defer(ephemeral=True)

        cfg = self.get_guild_config(interaction.guild)
        allowed = cfg.get("allowed_domains", [])
        blocked = cfg.get("blocked_domains", [])
        log_id = cfg.get("log_channel_id")
        log_channel = interaction.guild.get_channel(log_id) if log_id else None

        allowed_str = ", ".join(allowed) if allowed else "—"
        blocked_str = ", ".join(blocked) if blocked else "—"
        log_str = log_channel.mention if log_channel else "не установлен"

        embed = discord.Embed(
            title="Настройки модерации ссылок",
            color=discord.Color.blue()
        )
        embed.add_field(name="Лог-канал", value=log_str, inline=False)
        embed.add_field(name="Разрешённые домены", value=allowed_str, inline=False)
        embed.add_field(name="Запрещённые домены", value=blocked_str, inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moder(bot))