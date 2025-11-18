# uinfo.py
import discord
from discord import app_commands
from discord.ext import commands


class UserInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="uinfo", description="Показать информацию о пользователе")
    @app_commands.describe(user="Пользователь для просмотра информации (по умолчанию - вы)")
    async def uinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        # Если пользователь не указан, используем того, кто вызвал команду
        user = user or interaction.user

        em = discord.Embed(
            title="**👤 Информация о пользователе**",
            color=user.color if user.color != discord.Color.default() else discord.Color.blurple()
        )

        # Задержка бота
        ws_ms = int(self.bot.latency * 1000)

        # Основная информация
        em.add_field(name="Имя:", value=user.mention, inline=True)
        em.add_field(name="ID:", value=user.id, inline=True)
        em.add_field(name="Пинг бота:", value=f"{ws_ms} ms", inline=True)

        # Даты
        em.add_field(
            name="Присоединился к серверу:",
            value=f'<t:{int(user.joined_at.timestamp())}:D>\n(<t:{int(user.joined_at.timestamp())}:R>)',
            inline=True
        )
        em.add_field(
            name="Создал дискорд:",
            value=f'<t:{int(user.created_at.timestamp())}:D>\n(<t:{int(user.created_at.timestamp())}:R>)',
            inline=True
        )

        # Статус и активность
        status_emojis = {
            'online': '🟢',
            'idle': '🟡',
            'dnd': '🔴',
            'offline': '⚫'
        }
        status_text = {
            'online': 'В сети',
            'idle': 'Не активен',
            'dnd': 'Не беспокоить',
            'offline': 'Не в сети'
        }

        status = str(user.status)
        em.add_field(
            name="Статус:",
            value=f"{status_emojis.get(status, '⚫')} {status_text.get(status, 'Неизвестно')}",
            inline=True
        )

        # Роли пользователя (первые 5 ролей, исключая @everyone)
        roles = [role.mention for role in user.roles[1:6]]  # Пропускаем @everyone
        if roles:
            roles_text = ", ".join(roles)
            if len(user.roles) > 6:
                roles_text += f" и ещё {len(user.roles) - 6}"
        else:
            roles_text = "Нет ролей"

        em.add_field(name=f"Роли ({len(user.roles) - 1}):", value=roles_text, inline=False)

        # Дополнительная информация
        em.add_field(name="Бот:", value="Да" if user.bot else "Нет", inline=True)
        em.add_field(name="Буст сервера:", value="Да" if user.premium_since else "Нет", inline=True)

        # Аватар пользователя
        if user.avatar:
            em.set_thumbnail(url=user.avatar.url)
        elif user.display_avatar:
            em.set_thumbnail(url=user.display_avatar.url)

        # Футер с временем выполнения
        em.set_footer(text=f"Запрос от {interaction.user.display_name}",
                      icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=em)


async def setup(bot):
    await bot.add_cog(UserInfo(bot))