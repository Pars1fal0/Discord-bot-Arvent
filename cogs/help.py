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
        em.add_field(
            name="No categories:",
            value=(
                "`!help` - show available commands\n"
                "`!sinfo` - show information about the server\n"
                "`!uinfo` - show information about the user"
            ),
            inline=False
        )

        is_admin = False
        if ctx.guild and isinstance(ctx.author, discord.Member):
            is_admin = ctx.author.guild_permissions.administrator

        if not is_admin:
            em.add_field(
                name="Streaming tools:",
                value=(
                    "`!stream` - list available stream commands\n"
                    "`!stream linktwitch <login>` - link your Twitch account\n"
                    "`!stream linkyoutube <channel_id>` - link your YouTube channel\n"
                    "`!stream show [member]` - show linked accounts (defaults to you)\n"
                    "`!stream unlink <twitch|youtube>` - remove a linked platform"
                ),
                inline=False
            )

        await ctx.send(embed=em)


async def setup(bot):
    await bot.add_cog(HelpInfo(bot))
