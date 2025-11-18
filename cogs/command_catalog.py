import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import CheckFailure


class CommandCatalog(commands.Cog):
    """Команда для администраторов, которая выводит все доступные команды бота."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="commands", description="Показать полный список команд бота (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def list_all_commands(self, interaction: discord.Interaction) -> None:
        """Показать полный список команд бота (для администраторов)."""
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📚 Полный список команд",
            description=(
                "Доступно только администраторам. Ниже перечислены все команды, "
                "которые сейчас загружены у бота."
            ),
            color=discord.Color.dark_gold(),
        )

        # Получаем все слэш-команды
        commands_list = []
        for command in self.bot.tree.get_commands():
            if isinstance(command, app_commands.Command):
                commands_list.append(command)
            elif isinstance(command, app_commands.Group):
                # Обрабатываем группы команд
                for subcommand in command.commands:
                    commands_list.append(subcommand)

        # Сортируем команды по имени
        commands_list.sort(key=lambda cmd: cmd.qualified_name)

        lines = []
        for command in commands_list:
            # Формируем сигнатуру команды
            signature = f"/{command.qualified_name}"

            # Добавляем параметры
            if command.parameters:
                params = []
                for param in command.parameters:
                    if param.required:
                        params.append(f"<{param.name}>")
                    else:
                        params.append(f"[{param.name}]")
                signature += " " + " ".join(params)

            description = command.description or "Описание отсутствует."
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

        await interaction.followup.send(embed=embed, ephemeral=True)

    @list_all_commands.error
    async def list_all_commands_error(
            self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if isinstance(error, CheckFailure):
            await interaction.response.send_message(
                "❌ Эта команда доступна только администраторам сервера.",
                ephemeral=True
            )
        else:
            # Логируем другие ошибки
            print(f"Ошибка в команде commands: {error}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при выполнении команды.",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandCatalog(bot))