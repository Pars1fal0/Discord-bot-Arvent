import discord
from discord.ext import commands
import asyncio

class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def sinfo(self, ctx):
        em = discord.Embed(
            title="**🖥️Discord server statistics**",
            color=discord.Color.dark_blue()
        )
        guild = ctx.guild
        em.add_field(name="Server name", value=f'`{guild}`', inline=True)
        em.add_field(name="Owner", value=f'`{guild.owner}`', inline=True)
        em.add_field(name="Members\n", value=f'`{guild.member_count}`', inline=True)
        em.add_field(name="Roles", value=f'`{len(guild.roles)}`', inline=True)
        em.add_field(name="Channels", value=f'`{len(guild.channels)}`', inline=True)
        em.add_field(name="Created", value=f'`{guild.created_at.strftime("%Y-%m-%d %H:%M:%S")}`', inline=True)
        await ctx.send(embed=em)

async def setup(bot):
    await bot.add_cog(ServerInfo(bot))