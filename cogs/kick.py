import discord
from discord.ext import commands
import asyncio

class Moderation2(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        try:
            await member.send(f"Вы были кикнуты с сервера {ctx.guild.name}. Причина: {reason}")
        except:
            pass

        await member.kick(reason=reason)

        embed = discord.Embed(
            title="Пользователь кикнут",
            description=f"{member.mention} был кикнут",
            color=discord.Color.orange()
        )
        embed.add_field(name="Причина", value=reason or "Не указана")
        embed.add_field(name="Модератор", value=ctx.author.mention)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation2(bot))