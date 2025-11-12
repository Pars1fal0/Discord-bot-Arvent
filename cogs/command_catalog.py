import discord
from discord.ext import commands
from discord.ext.commands import CheckFailure


class CommandCatalog(commands.Cog):
    """Команда для администраторов, которая выводит все доступные команды бота."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="commands", aliases=("allcommands",))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def list_all_commands(self, ctx: commands.Context) -> None:
        """Показать полный список команд бота (для администраторов)."""
        embed = discord.Embed(
            title="📚 Полный список команд",
            description=(
                "Доступно только администраторам. Ниже перечислены все команды, "
                "которые сейчас загружены у бота."
            ),
            color=discord.Color.dark_gold(),
        )

        commands_list = sorted(
            (command for command in self.bot.commands if not command.hidden),
            key=lambda command: command.qualified_name,
        )

        lines = []
        for command in commands_list:
            signature = f"!{command.qualified_name}"
            if command.signature:
                signature += f" {command.signature}"

            description = command.help or command.description or "Описание отсутствует."
            lines.append(f"**{signature}**\n{description}")

        if lines:
            description_text = "\n\n".join(lines)
            if len(description_text) <= 4096:
                embed.description = (
                    embed.description + "\n\n" + description_text
                )
            else:
                chunks = []
                current = ""
                for line in lines:
                    entry = line + "\n\n"
                    if len(current) + len(entry) > 4096:
                        chunks.append(current.rstrip())
                        current = entry
                    else:
                        current += entry
                if current:
                    chunks.append(current.rstrip())

                embed.description = embed.description + "\n\n" + chunks[0]
                for index, chunk in enumerate(chunks[1:], start=2):
                    embed.add_field(
                        name=f"Продолжение {index}", value=chunk, inline=False
                    )
        else:
            embed.add_field(
                name="Команды не найдены",
                value="Не удалось обнаружить зарегистрированные команды.",
                inline=False,
            )

        await ctx.send(embed=embed)

    @list_all_commands.error
    async def list_all_commands_error(
        self, ctx: commands.Context, error: Exception
    ) -> None:
        if isinstance(error, CheckFailure):
            await ctx.send("❌ Эта команда доступна только администраторам сервера.")
        else:
            raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandCatalog(bot))

