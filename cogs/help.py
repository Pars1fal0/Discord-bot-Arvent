import discord
from discord.ext import commands


class HelpInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx):
        em = discord.Embed(
            title="**📘 Available Commands**",
            color=discord.Color.blurple()
        )
        em.add_field(name="No categories:", value=f"`!help` - show available commands\n"
                                                  f"`!sinfo` - show information about the server\n"
                                                  f"`!uinfo` - show information about the user\n")

        await ctx.send(embed=em)
async def setup(bot):
    await bot.add_cog(HelpInfo(bot))