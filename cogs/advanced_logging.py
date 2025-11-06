import discord
from discord.ext import commands
import datetime
import aiohttp
import io


class AdvancedLogging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        """Логирование массового удаления сообщений"""
        if not messages or not messages[0].guild:
            return

        guild = messages[0].guild
        channel = messages[0].channel

        # Создаем текстовый файл с удаленными сообщениями
        log_content = f"Массовое удаление сообщений в #{channel.name}\n"
        log_content += f"Время: {datetime.datetime.utcnow()}\n"
        log_content += f"Количество сообщений: {len(messages)}\n"
        log_content += "=" * 50 + "\n\n"

        for msg in sorted(messages, key=lambda x: x.created_at):
            if not msg.author.bot:
                log_content += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content}\n"
                if msg.attachments:
                    log_content += f"📎 Вложения: {len(msg.attachments)}\n"
                log_content += "\n"

        # Создаем файл
        file = discord.File(
            io.BytesIO(log_content.encode('utf-8')),
            filename=f"bulk_delete_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        embed = discord.Embed(
            title="💥 Массовое удаление сообщений",
            color=discord.Color.dark_red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Канал", value=channel.mention, inline=True)
        embed.add_field(name="Количество", value=len(messages), inline=True)

        log_channel = discord.utils.get(guild.text_channels, name="логи")
        if log_channel:
            await log_channel.send(embed=embed, file=file)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """Логирование создания приглашения"""
        embed = discord.Embed(
            title="📨 Создано приглашение",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Создатель", value=invite.inviter.mention, inline=True)
        embed.add_field(name="Канал", value=invite.channel.mention, inline=True)
        embed.add_field(name="Код", value=invite.code, inline=True)

        if invite.max_age > 0:
            embed.add_field(name="Истекает",
                            value=f"<t:{int((datetime.datetime.utcnow() + datetime.timedelta(seconds=invite.max_age)).timestamp())}:R>",
                            inline=True)
        else:
            embed.add_field(name="Истекает", value="Никогда", inline=True)

        if invite.max_uses > 0:
            embed.add_field(name="Макс. использований", value=invite.max_uses, inline=True)
        else:
            embed.add_field(name="Макс. использований", value="Неограничено", inline=True)

        log_channel = discord.utils.get(invite.guild.text_channels, name="логи")
        if log_channel:
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """Логирование удаления приглашения"""
        embed = discord.Embed(
            title="🗑️ Приглашение удалено",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Канал", value=invite.channel.mention, inline=True)
        embed.add_field(name="Код", value=invite.code, inline=True)

        log_channel = discord.utils.get(invite.guild.text_channels, name="логи")
        if log_channel:
            await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdvancedLogging(bot))