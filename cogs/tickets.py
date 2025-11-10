# cogs/tickets.py
import asyncio
import datetime
import json
import os
from io import StringIO

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput

# ==== НАСТРОЙКИ, КОТОРЫЕ ПОКА ОСТАВИМ КОНСТАНТАМИ ====
LOG_CHANNEL_ID = 1437390123741352057  # канал для логов тикетов (укажи свой)

CATEGORY_TITLES = {
    "bug": "Баг",
    "idea": "Идея",
    "complaint": "Жалоба",
}

CONFIG_FILE = "ticket_config.json"

DEFAULT_CONFIG = {
    "bug": {"support_role_id": None, "category_id": None},
    "idea": {"support_role_id": None, "category_id": None},
    "complaint": {"support_role_id": None, "category_id": None},
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # подстрахуемся, что все ключи есть
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
                else:
                    data[k].setdefault("support_role_id", None)
                    data[k].setdefault("category_id", None)
            return data
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()


CONFIG = load_config()


def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=2)


def get_support_role_id_for_type(ticket_type: str):
    cfg = CONFIG.get(ticket_type)
    if not cfg:
        return None
    return cfg.get("support_role_id")


def get_category_id_for_type(ticket_type: str):
    cfg = CONFIG.get(ticket_type)
    if not cfg:
        return None
    return cfg.get("category_id")


def get_all_support_role_ids():
    ids = set()
    for cfg in CONFIG.values():
        rid = cfg.get("support_role_id")
        if rid:
            ids.add(rid)
    return ids


def member_is_support(member: discord.Member) -> bool:
    support_ids = get_all_support_role_ids()
    if not support_ids:
        return False
    return any(role.id in support_ids for role in member.roles)


class TicketCloseView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Закрыть тикет",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_close_button"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: Button
    ):
        channel = interaction.channel
        guild = interaction.guild

        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "Эту кнопку нужно нажимать в текстовом канале тикета.",
                ephemeral=True
            )

        member = interaction.user

        is_support = member_is_support(member)
        is_admin = member.guild_permissions.administrator

        if not (is_support or is_admin):
            return await interaction.response.send_message(
                "Только поддержка или администратор могут закрывать тикеты.",
                ephemeral=True
            )

        await interaction.response.defer()

        # Генерация транскрипта
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        transcript = StringIO()
        transcript.write(f"Тикет: #{channel.name}\nID: {channel.id}\n")
        transcript.write(f"Закрыл: {member} ({member.id})\n")
        transcript.write(f"Дата закрытия: {datetime.datetime.utcnow()} UTC\n\n")
        transcript.write("---- Сообщения ----\n")

        async for msg in channel.history(limit=None, oldest_first=True):
            author = f"{msg.author} ({msg.author.id})"
            content = msg.content if msg.content else ""
            transcript.write(f"[{msg.created_at}] {author}: {content}\n")
            for a in msg.attachments:
                transcript.write(f"    [Файл] {a.url}\n")

        transcript.seek(0)

        if log_channel:
            file = discord.File(
                fp=transcript,
                filename=f"ticket-{channel.id}.txt"
            )
            embed = discord.Embed(
                title="Тикет закрыт",
                description=f"Канал: {channel.mention}\nЗакрыл: {member.mention}",
                color=discord.Color.red()
            )
            await log_channel.send(embed=embed, file=file)

        await channel.send("Тикет будет удалён через 5 секунд...")
        await asyncio.sleep(5)
        await channel.delete(reason=f"Тикет закрыт {member}")


class TicketCreateModal(Modal):
    def __init__(self, bot: commands.Bot, category: str):
        self.bot = bot
        self.category = category

        title = f"Тикет: {CATEGORY_TITLES.get(category, 'Вопрос')}"
        super().__init__(title=title, timeout=300)

        self.subject = TextInput(
            label="Кратко опиши проблему/идею",
            placeholder="Например: Музыка не воспроизводится",
            max_length=100
        )
        self.description = TextInput(
            label="Подробное описание",
            style=discord.TextStyle.paragraph,
            placeholder="Что именно произошло, когда, какие команды/действия были?",
            max_length=1000
        )

        self.add_item(self.subject)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        # Проверяем наличие категории для данного типа тикета
        cat_id = get_category_id_for_type(self.category)
        if not cat_id:
            return await interaction.response.send_message(
                "Для этого типа тикета ещё не настроена категория каналов. "
                "Обратись к администратору.",
                ephemeral=True
            )

        category_channel = guild.get_channel(cat_id)
        if not isinstance(category_channel, discord.CategoryChannel):
            return await interaction.response.send_message(
                "Категория для тикетов настроена неверно. Обратись к администратору.",
                ephemeral=True
            )

        # Проверяем, есть ли уже тикет у пользователя
        existing = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{user.id}"
        )
        if existing:
            return await interaction.response.send_message(
                f"У тебя уже есть тикет: {existing.mention}",
                ephemeral=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            )
        }

        support_role_id = get_support_role_id_for_type(self.category)
        support_role = guild.get_role(support_role_id) if support_role_id else None
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        channel = await guild.create_text_channel(
            name=f"ticket-{user.id}",
            category=category_channel,
            overwrites=overwrites,
            reason=f"Тикет ({self.category}) от {user} ({user.id})"
        )

        cat_title = CATEGORY_TITLES.get(self.category, "Вопрос")

        embed = discord.Embed(
            title=f"🎫 Новый тикет — {cat_title}",
            description=(
                f"**Тема:** {self.subject.value}\n\n"
                f"**Описание:**\n{self.description.value}\n\n"
                f"{user.mention}, ожидай ответа поддержки.\n"
                "_Не спамь и не создавай дубликаты тикетов._"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"ID пользователя: {user.id}")

        view = TicketCloseView(self.bot)

        content = user.mention
        if support_role:
            content += f" | {support_role.mention}"

        await channel.send(
            content=content,
            embed=embed,
            view=view
        )

        await interaction.response.send_message(
            f"Тикет создан: {channel.mention}",
            ephemeral=True
        )


class TicketCategorySelect(Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Баг",
                value="bug",
                emoji="🐛",
                description="Что-то не работает / ошибка"
            ),
            discord.SelectOption(
                label="Идея",
                value="idea",
                emoji="💡",
                description="Предложение по улучшению"
            ),
            discord.SelectOption(
                label="Жалоба",
                value="complaint",
                emoji="⚠️",
                description="Жалоба на участника/модерацию"
            ),
        ]
        super().__init__(
            placeholder="Выбери категорию тикета…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        modal = TicketCreateModal(self.bot, category)
        await interaction.response.send_modal(modal)


class TicketCategoryView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=60)
        self.add_item(TicketCategorySelect(bot))


class TicketPanelView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Создать тикет",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket_create_button"
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: Button
    ):
        guild = interaction.guild
        user = interaction.user

        # Проверяем, есть ли уже тикет у пользователя
        existing = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{user.id}"
        )
        if existing:
            return await interaction.response.send_message(
                f"У тебя уже есть тикет: {existing.mention}",
                ephemeral=True
            )

        # Хоть одна категория должна быть настроена, иначе смысла нет
        has_any_category = any(
            get_category_id_for_type(t) for t in CONFIG.keys()
        )
        if not has_any_category:
            return await interaction.response.send_message(
                "Ни для одного типа тикетов не настроена категория каналов. "
                "Обратись к администратору.",
                ephemeral=True
            )

        view = TicketCategoryView(self.bot)
        await interaction.response.send_message(
            "Выбери категорию тикета:",
            view=view,
            ephemeral=True
        )


class Tickets(commands.Cog):
    """Система тикетов с категориями и настраиваемыми ролями"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # === Панель тикетов ===

    @commands.command(name="ticketpanel")
    @commands.has_permissions(administrator=True)
    async def ticket_panel_cmd(self, ctx: commands.Context):
        """Отправить панель с кнопкой создания тикета."""
        embed = discord.Embed(
            title="Поддержка",
            description=(
                "Нажми на кнопку ниже, чтобы создать тикет.\n\n"
                "Сначала выбери категорию (баг, идея, жалоба), "
                "а затем опиши проблему в форме."
            ),
            color=discord.Color.blurple()
        )
        view = TicketPanelView(self.bot)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="ticketpanel", description="Отправить панель тикетов")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Поддержка",
            description=(
                "Нажми на кнопку ниже, чтобы создать тикет.\n\n"
                "Сначала выбери категорию (баг, идея, жалоба), "
                "а затем заполни форму."
            ),
            color=discord.Color.blurple()
        )
        view = TicketPanelView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    # === КОМАНДЫ НАСТРОЙКИ РОЛЕЙ И КАТЕГОРИЙ ===

    @commands.command(name="ticketsetrole")
    @commands.has_permissions(administrator=True)
    async def ticket_set_role(
        self,
        ctx: commands.Context,
        ticket_type: str,
        role: discord.Role
    ):
        """
        Установить роль поддержки для типа тикета.
        Пример: !ticketsetrole bug @Dev
        """
        tt = ticket_type.lower()
        if tt not in CONFIG:
            return await ctx.send(
                f"Неизвестный тип тикета: `{ticket_type}`. "
                f"Доступные: {', '.join(CONFIG.keys())}"
            )

        CONFIG[tt]["support_role_id"] = role.id
        save_config()
        await ctx.send(
            f"Для типа `{tt}` установлена роль поддержки {role.mention}"
        )

    @commands.command(name="ticketsetcat")
    @commands.has_permissions(administrator=True)
    async def ticket_set_category(
        self,
        ctx: commands.Context,
        ticket_type: str,
        category: discord.CategoryChannel
    ):
        """
        Установить дискорд-категорию каналов для типа тикета.
        Пример: !ticketsetcat bug #категория_багов
        (нужно указать именно категорию, не текстовый канал)
        """
        tt = ticket_type.lower()
        if tt not in CONFIG:
            return await ctx.send(
                f"Неизвестный тип тикета: `{ticket_type}`. "
                f"Доступные: {', '.join(CONFIG.keys())}"
            )

        CONFIG[tt]["category_id"] = category.id
        save_config()
        await ctx.send(
            f"Для типа `{tt}` установлена категория каналов: **{category.name}**"
        )

    @commands.command(name="ticketconfig")
    @commands.has_permissions(administrator=True)
    async def ticket_show_config(self, ctx: commands.Context):
        """Показать текущую конфигурацию тикетов."""
        lines = []
        for tt, cfg in CONFIG.items():
            role_id = cfg.get("support_role_id")
            cat_id = cfg.get("category_id")

            role_str = f"<@&{role_id}>" if role_id else "не задана"
            cat_str = f"<#{cat_id}>" if cat_id else "не задана"

            lines.append(f"**{tt}** — роль: {role_str}, категория: {cat_str}")

        embed = discord.Embed(
            title="Конфиг тикетов",
            description="\n".join(lines) if lines else "Пусто",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
    bot.add_view(TicketPanelView(bot))
    bot.add_view(TicketCloseView(bot))
