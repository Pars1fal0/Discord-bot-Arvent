import re
import json
import datetime
from collections import defaultdict, deque
from urllib.parse import urlparse
import asyncio
import typing as t

import discord
from discord.ext import commands

WARNINGS_FILE = "warnings.json"
CONFIG_FILE = "moderation_config.json"

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

SPAM_WINDOW = 10   # окно для антифлуда (сек)
SPAM_THRESHOLD = 3 # сколько сообщений за SPAM_WINDOW считается флудом

FLOOD_MUTE_MINUTES = 5  # <<< Мьют при флуде (в минутах)

# Наказания по количеству предупреждений (можно настроить)
# Сейчас: при 3 варнах → mute (через PUNISHMENTS), остальное выключено
PUNISHMENTS = {
    3: "mute"
}
MAX_WARNINGS = max(PUNISHMENTS.keys())
AUTO_MUTE_MINUTES = 10  # длительность авто-мьюта по варну из PUNISHMENTS

URL_REGEX = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)


class Moder(commands.Cog):
    """
    Модерация:
    - анти-капс / анти-флуд / фильтр ссылок
    - система предупреждений
    - лог-канал
    - настраиваемые списки доменов
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = self.load_warnings()
        self.config = self.load_config()
        # user_messages[guild_id][user_id] = deque[timestamps]
        self.user_messages: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(deque))
        # <<< Запоминаем, когда последний раз наказывали за флуд, чтобы не спамить варнами
        self.last_flood: dict[int, dict[int, float]] = defaultdict(dict)

    # ===== Файлы предупреждений и конфигурации =====

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
        """True, если пользователь флудит."""
        now = datetime.datetime.utcnow().timestamp()
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
        """Парсим домены из текста + "голые" заблокированные."""
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
            timestamp=datetime.datetime.utcnow()
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

    # ===== Роль Muted (как в твоём Mute-коге) =====

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

    async def auto_role_unmute(self, member: discord.Member, delay: int):
        """Авто-снятие роли Muted через delay секунд."""
        await asyncio.sleep(delay)

        try:
            mute_role = discord.utils.get(member.guild.roles, name="Muted")
            if mute_role and mute_role in member.roles:
                await member.remove_roles(mute_role, reason="Авто-размьют (по истечении времени мьюта)")
                try:
                    dm_embed = discord.Embed(
                        title="🔊 Автоматический размьют",
                        description=f"Ваш мьют на сервере **{member.guild.name}** истёк!",
                        color=discord.Color.green()
                    )
                    await member.send(embed=dm_embed)
                except Exception:
                    pass
        except Exception:
            # если вышел с сервера / удалена роль и т.п.
            pass

    # ===== Наказания по варнам (mute/kick/ban) =====

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

        # --- MUTE через роль Muted (по системе varns) ---
        if action == "mute":
            mute_role = await self.create_mute_role(guild)
            if not mute_role:
                await source_channel.send("❌ Не удалось создать или найти роль для мьюта!")
                return

            if mute_role in member.roles:
                await source_channel.send(f"ℹ️ {member.mention} уже замьючен(а).")
                return

            duration_sec = AUTO_MUTE_MINUTES * 60
            unmute_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_sec)

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
                dm_embed = discord.Embed(
                    title="⏰ Вы были временно замьючены",
                    description=f"На сервере **{guild.name}**",
                    color=discord.Color.orange()
                )
                dm_embed.add_field(name="Длительность", value=f"{AUTO_MUTE_MINUTES} мин.", inline=True)
                dm_embed.add_field(name="Размут", value=f"<t:{int(unmute_time.timestamp())}:R>", inline=True)
                dm_embed.add_field(name="Причина", value=base_reason, inline=False)
                await member.send(embed=dm_embed)
            except Exception:
                pass

            # авто-размьют
            self.bot.loop.create_task(self.auto_role_unmute(member, duration_sec))

        # (kick/ban сейчас не используются, т.к. PUNISHMENTS = {3: "mute"}, но логика оставлена)
        # после достижения максимума варнов — сбрасываем (после применения наказания)
        if warn_count >= MAX_WARNINGS:
            self.clear_warnings(guild.id, member.id)

    async def auto_warn(self, message: discord.Message, reason: str):
        """
        Общий варн (капс/ссылки и т.п.) + проверка PUNISHMENTS.
        Для флуда используется отдельная логика, чтобы не выдавать по несколько варнов.
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

        # варн за флуд
        warn_count = self.add_warning(guild.id, member.id)
        reason = "флуд (слишком много сообщений за короткое время)"

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

        # мут на FLOOD_MUTE_MINUTES (отдельно от PUNISHMENTS)
        mute_role = await self.create_mute_role(guild)
        if not mute_role:
            await channel.send("❌ Не удалось создать или найти роль для мьюта!")
            return

        if mute_role in member.roles:
            return  # уже замьючен, не дублируем

        duration_sec = FLOOD_MUTE_MINUTES * 60
        unmute_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_sec)

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
            dm_embed = discord.Embed(
                title="⏰ Вы были временно замьючены",
                description=f"На сервере **{guild.name}**",
                color=discord.Color.orange()
            )
            dm_embed.add_field(name="Длительность", value=f"{FLOOD_MUTE_MINUTES} мин.", inline=True)
            dm_embed.add_field(name="Размут", value=f"<t:{int(unmute_time.timestamp())}:R>", inline=True)
            dm_embed.add_field(name="Причина", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except Exception:
            pass

        # авто-размьют
        self.bot.loop.create_task(self.auto_role_unmute(member, duration_sec))

        # при достижении MAX_WARNINGS — чистим варны (чтобы не копились вечно)
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
            now = datetime.datetime.utcnow().timestamp()
            guild_id = message.guild.id
            user_id = message.author.id

            last = self.last_flood[guild_id].get(user_id, 0.0)

            # Если уже наказывали за флуд в ближайшие SPAM_WINDOW сек —
            # просто удаляем сообщение, НО БЕЗ доп. варнов/мьютов.
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

    # ===== Команды предупреждений =====

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn_command(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Нарушение правил"):
        """Выдать варн вручную (и автоматически наказать по PUNISHMENTS)."""
        warn_count = self.add_warning(ctx.guild.id, member.id)

        # ЛС пользователю
        dm_text = (
            f"⚠️ Ты получил предупреждение на сервере **{ctx.guild.name}** "
            f"за **{reason}** (**{warn_count}/{MAX_WARNINGS}**)."
        )
        try:
            await member.send(dm_text)
        except discord.Forbidden:
            pass

        # Краткое подтверждение в канал для модератора
        await ctx.send(
            f"✅ Предупреждение выдано пользователю {member.mention} "
            f"(**{warn_count}/{MAX_WARNINGS}**)."
        )

        await self.log_action(
            ctx.guild,
            member=member,
            action="Предупреждение",
            reason=reason,
            moderator=ctx.author,
            extra=f"Всего предупреждений: {warn_count}/{MAX_WARNINGS}",
        )

        await self.apply_punishment(member, warn_count, reason, ctx.channel, auto=False)

    @commands.command(name="unwarn")
    @commands.has_permissions(manage_messages=True)
    async def unwarn_command(self, ctx: commands.Context, member: discord.Member):
        """Сбросить все варны у пользователя."""
        self.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(f"✅ Все предупреждения с {member.mention} сняты.")

        await self.log_action(
            ctx.guild,
            member=member,
            action="Снятие предупреждений",
            reason="Сброс варнов командой unwarn",
            moderator=ctx.author,
        )

    @commands.command(name="warnings")
    @commands.has_permissions(manage_messages=True)
    async def warnings_command(self, ctx: commands.Context, member: discord.Member = None):
        """Посмотреть кол-во варнов."""
        member = member or ctx.author
        count = self.get_warn_count(ctx.guild.id, member.id)
        await ctx.send(f"ℹ️ У {member.mention} сейчас **{count}** предупреждений (из {MAX_WARNINGS}).")

    # ===== Команды настройки (лог-канал и домены) =====

    @commands.command(name="setlog")
    @commands.has_permissions(manage_guild=True)
    async def setlog_command(self, ctx: commands.Context, channel: discord.TextChannel):
        """Установить лог-канал для модерации."""
        cfg = self.get_guild_config(ctx.guild)
        cfg["log_channel_id"] = channel.id
        self.save_config()
        await ctx.send(f"✅ Лог-канал для модерации установлен: {channel.mention}")

    @commands.command(name="adddomain")
    @commands.has_permissions(manage_guild=True)
    async def adddomain_command(self, ctx: commands.Context, domain: str):
        """
        Добавить домен в белый список (разрешённые ссылки).
        Пример: !adddomain youtube.com
        """
        domain = domain.lower().strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            parsed = urlparse(domain)
            domain = parsed.hostname or domain
        if domain.startswith("www."):
            domain = domain[4:]

        cfg = self.get_guild_config(ctx.guild)
        allowed = set(cfg.get("allowed_domains", []))
        blocked = set(cfg.get("blocked_domains", []))

        if domain in blocked:
            blocked.remove(domain)

        allowed.add(domain)
        cfg["allowed_domains"] = sorted(allowed)
        cfg["blocked_domains"] = sorted(blocked)
        self.save_config()

        await ctx.send(f"✅ Домен `{domain}` добавлен в **разрешённые**.")

    @commands.command(name="blockdomain")
    @commands.has_permissions(manage_guild=True)
    async def blockdomain_command(self, ctx: commands.Context, domain: str):
        """
        Добавить домен в чёрный список (запрещённые ссылки).
        Пример: !blockdomain t.me
        """
        domain = domain.lower().strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            parsed = urlparse(domain)
            domain = parsed.hostname or domain
        if domain.startswith("www."):
            domain = domain[4:]

        cfg = self.get_guild_config(ctx.guild)
        allowed = set(cfg.get("allowed_domains", []))
        blocked = set(cfg.get("blocked_domains", []))

        if domain in allowed:
            allowed.remove(domain)

        blocked.add(domain)
        cfg["allowed_domains"] = sorted(allowed)
        cfg["blocked_domains"] = sorted(blocked)
        self.save_config()

        await ctx.send(f"✅ Домен `{domain}` добавлен в **запрещённые**.")

    @commands.command(name="domains")
    @commands.has_permissions(manage_guild=True)
    async def domains_command(self, ctx: commands.Context):
        """Показать текущие списки доменов и лог-канал."""
        cfg = self.get_guild_config(ctx.guild)
        allowed = cfg.get("allowed_domains", [])
        blocked = cfg.get("blocked_domains", [])
        log_id = cfg.get("log_channel_id")
        log_channel = ctx.guild.get_channel(log_id) if log_id else None

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

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moder(bot))
