import discord
from discord.ext import commands
import asyncio
from typing import Optional
import re

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Забанить пользователя"""
        try:
            await member.send(f"Вы были забанены на сервере {ctx.guild.name}. Причина: {reason}")
        except:
            pass

        await member.ban(reason=reason)

        embed = discord.Embed(
            title="Пользователь забанен",
            description=f"{member.mention} был забанен.",
            color=discord.Color.red()
        )
        embed.add_field(name="Причина", value=reason or "Не указана")
        embed.add_field(name="Модератор", value=ctx.author.mention)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, target: str):
        """
        Разбанить пользователя по ID, упоминанию, имени (username),
        имени с тегом (name#1234) или global_name.
        Поддерживает частичные совпадения (если ровно один кандидат).
        """
        guild = ctx.guild

        def norm(s: Optional[str]) -> str:
            return (s or "").strip().lower()

        # ----- 1) Сначала пробуем извлечь ID / упоминание -----
        # Форматы: 1234567890, <@1234567890>, <@!1234567890>
        m = re.fullmatch(r"(?:<@!?(?P<id1>\d+)>|(?P<id2>\d+))", target.strip())
        if m:
            uid = int(m.group("id1") or m.group("id2"))
            try:
                user = await self.bot.fetch_user(uid)
            except Exception:
                user = discord.Object(id=uid)

            # Попытка разбанить напрямую по ID
            try:
                await guild.unban(user, reason=f"Unban by {ctx.author} ({ctx.author.id})")
            except discord.NotFound:
                await ctx.send("❌ Этот пользователь не в бан-листе.")
                return
            except discord.Forbidden:
                await ctx.send("❌ У бота нет прав для разбанивания этого пользователя.")
                return
            except Exception as e:
                await ctx.send(f"❌ Ошибка при разбане: `{e}`")
                return

            # Красивый эмбед
            if isinstance(user, discord.Object):
                try:
                    user = await self.bot.fetch_user(user.id)
                except Exception:
                    pass

            embed = discord.Embed(
                title="Пользователь разбанен",
                description=f"{getattr(user, 'mention', f'`{user}`')} был разбанен.",
                color=discord.Color.green()
            )
            embed.add_field(name="Модератор", value=ctx.author.mention)
            await ctx.send(embed=embed)
            return

        # ----- 2) Готовим список банов (новый API: async-итератор) -----
        bans: List[discord.guild.BanEntry] = [b async for b in guild.bans(limit=None)]
        if not bans:
            await ctx.send("ℹ️ В бан-листе никого нет.")
            return

        q = norm(target)

        # ----- 3) Поиск ТОЛЬКО по точным совпадениям -----
        # Сравниваем со строковым представлением (legacy name#1234), username и global_name
        def u_exact_match(u: discord.User) -> bool:
            return (
                    q == norm(str(u))  # например: "name#1234" (старые аккаунты)
                    or q == norm(u.name)  # username (без #)
                    or q == norm(getattr(u, "global_name", None))  # отображаемое имя (global name)
            )

        exact = [b for b in bans if u_exact_match(b.user)]
        if len(exact) == 1:
            user = exact[0].user
        elif len(exact) > 1:
            # Слишком много точных совпадений — просим указать ID
            lines = []
            for b in exact[:10]:
                u = b.user
                lines.append(f"- `{u}` (ID: `{u.id}`)")
            msg = "⚠️ Найдено несколько точных совпадений по имени. Уточни ID:\n" + "\n".join(lines)
            if len(exact) > 10:
                msg += f"\n… и ещё {len(exact) - 10}"
            await ctx.send(msg)
            return
        else:
            # ----- 4) Если точных нет — пробуем УНИКАЛЬНОЕ частичное совпадение -----
            def u_partial(u: discord.User) -> bool:
                return (
                        q in norm(str(u))
                        or q in norm(u.name)
                        or q in norm(getattr(u, "global_name", None))
                )

            partial = [b for b in bans if u_partial(b.user)]

            if len(partial) == 1:
                user = partial[0].user
            elif len(partial) > 1:
                # Много кандидатов — покажем список для выбора по ID
                lines = []
                for b in partial[:10]:
                    u = b.user
                    gn = getattr(u, "global_name", None)
                    gn_str = f" | global_name: {gn}" if gn else ""
                    lines.append(f"- `{u}` (username: `{u.name}`{gn_str}) — ID: `{u.id}`")
                msg = (
                        "⚠️ Найдено несколько пользователей по частичному совпадению. "
                        "Повтори команду с точным ID:\n" + "\n".join(lines)
                )
                if len(partial) > 10:
                    msg += f"\n… и ещё {len(partial) - 10}"
                await ctx.send(msg)
                return
            else:
                await ctx.send("❌ Пользователь не найден в бан-листе по такому имени. Укажи корректное имя или ID.")
                return

        # ----- 5) Разбан по найденному пользователю -----
        try:
            await guild.unban(user, reason=f"Unban by {ctx.author} ({ctx.author.id})")
        except discord.NotFound:
            await ctx.send("❌ Этот пользователь не числится в бан-листе.")
            return
        except discord.Forbidden:
            await ctx.send("❌ У бота нет прав для разбанивания этого пользователя.")
            return
        except Exception as e:
            await ctx.send(f"❌ Ошибка при разбане: `{e}`")
            return

        # Финальный эмбед
        try:
            # догружаем полноценного User (если вдруг пришёл кастомный объект)
            user = await self.bot.fetch_user(user.id)
        except Exception:
            pass

        embed = discord.Embed(
            title="Пользователь разбанен",
            description=f"{getattr(user, 'mention', f'`{user}`')} был разбанен.",
            color=discord.Color.green()
        )
        embed.add_field(name="Модератор", value=ctx.author.mention)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))