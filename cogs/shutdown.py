import discord
from discord.ext import commands
import asyncio
import os
import sys


class Shutdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def shutdowns(self, ctx):
        """Выключить бота (только для владельца)"""
        embed = discord.Embed(
            title="🔴 Выключение бота",
            description="Бот выключается...",
            color=discord.Color.red()
        )
        embed.add_field(name="Инициатор", value=ctx.author.mention, inline=True)
        embed.add_field(name="Время", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)

        await ctx.send(embed=embed)

        # Даем время на отправку сообщения
        await asyncio.sleep(1)

        print(f"🛑 Бот выключен пользователем {ctx.author} (ID: {ctx.author.id})")
        await self.bot.close()

    @commands.command()
    @commands.is_owner()
    async def restarts(self, ctx):
        """Перезагрузить бота (только для владельца)"""
        embed = discord.Embed(
            title="🔄 Перезагрузка бота",
            description="Бот перезагружается...",
            color=discord.Color.orange()
        )
        embed.add_field(name="Инициатор", value=ctx.author.mention, inline=True)
        embed.add_field(name="Время", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)

        await ctx.send(embed=embed)

        # Даем время на отправку сообщения
        await asyncio.sleep(1)

        print(f"🔄 Бот перезагружен пользователем {ctx.author} (ID: {ctx.author.id})")

        # Перезапуск бота
        os.execv(sys.executable, ['python'] + sys.argv)

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, cog: str = None):
        """Перезагрузить ког или все коги (только для владельца)"""
        if cog:
            # Перезагрузка конкретного кога
            try:
                await self.bot.reload_extension(f"cogs.{cog}")
                embed = discord.Embed(
                    title="✅ Ког перезагружен",
                    description=f"Ког `{cog}` успешно перезагружен!",
                    color=discord.Color.green()
                )
                print(f"🔄 Ког {cog} перезагружен пользователем {ctx.author}")
            except commands.ExtensionNotLoaded:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Ког `{cog}` не загружен!",
                    color=discord.Color.red()
                )
            except commands.ExtensionNotFound:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Ког `{cog}` не найден!",
                    color=discord.Color.red()
                )
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Ошибка перезагрузки",
                    description=f"Ошибка при перезагрузке кога `{cog}`: {str(e)}",
                    color=discord.Color.red()
                )
        else:
            # Перезагрузка всех когов
            success = []
            failed = []

            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    cog_name = filename[:-3]
                    try:
                        await self.bot.reload_extension(f'cogs.{cog_name}')
                        success.append(cog_name)
                    except Exception as e:
                        failed.append(f"{cog_name}: {str(e)}")

            embed = discord.Embed(
                title="🔄 Перезагрузка всех когов",
                color=discord.Color.blue()
            )

            if success:
                embed.add_field(
                    name="✅ Успешно перезагружены",
                    value="\n".join([f"`{cog}`" for cog in success]),
                    inline=False
                )

            if failed:
                embed.add_field(
                    name="❌ Ошибки перезагрузки",
                    value="\n".join([f"`{error}`" for error in failed]),
                    inline=False
                )

            print(f"🔄 Все коги перезагружены пользователем {ctx.author}")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def load(self, ctx, cog: str):
        """Загрузить ког (только для владельца)"""
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            embed = discord.Embed(
                title="✅ Ког загружен",
                description=f"Ког `{cog}` успешно загружен!",
                color=discord.Color.green()
            )
            print(f"📥 Ког {cog} загружен пользователем {ctx.author}")
        except commands.ExtensionAlreadyLoaded:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Ког `{cog}` уже загружен!",
                color=discord.Color.orange()
            )
        except commands.ExtensionNotFound:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Ког `{cog}` не найден!",
                color=discord.Color.red()
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка загрузки",
                description=f"Ошибка при загрузке кога `{cog}`: {str(e)}",
                color=discord.Color.red()
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def unload(self, ctx, cog: str):
        """Выгрузить ког (только для владельца)"""
        if cog == "shutdown":
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Нельзя выгрузить ког shutdown!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            await self.bot.unload_extension(f"cogs.{cog}")
            embed = discord.Embed(
                title="✅ Ког выгружен",
                description=f"Ког `{cog}` успешно выгружен!",
                color=discord.Color.orange()
            )
            print(f"📤 Ког {cog} выгружен пользователем {ctx.author}")
        except commands.ExtensionNotLoaded:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Ког `{cog}` не загружен!",
                color=discord.Color.red()
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка выгрузки",
                description=f"Ошибка при выгрузке кога `{cog}`: {str(e)}",
                color=discord.Color.red()
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def cogs_list(self, ctx):
        """Показать список всех когов (только для владельца)"""
        loaded_cogs = []
        unloaded_cogs = []

        # Получаем все файлы когов
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                cog_name = filename[:-3]
                if f"cogs.{cog_name}" in self.bot.extensions:
                    loaded_cogs.append(cog_name)
                else:
                    unloaded_cogs.append(cog_name)

        embed = discord.Embed(
            title="📚 Список когов",
            color=discord.Color.blue()
        )

        if loaded_cogs:
            embed.add_field(
                name="🟢 Загруженные коги",
                value="\n".join([f"`{cog}`" for cog in sorted(loaded_cogs)]),
                inline=True
            )

        if unloaded_cogs:
            embed.add_field(
                name="🔴 Незагруженные коги",
                value="\n".join([f"`{cog}`" for cog in sorted(unloaded_cogs)]),
                inline=True
            )

        embed.add_field(
            name="📋 Команды управления",
            value=(
                "`!load <ког>` - загрузить ког\n"
                "`!unload <ког>` - выгрузить ког\n"
                "`!reload <ког>` - перезагрузить ког\n"
                "`!reload` - перезагрузить все коги\n"
                "`!restart` - перезапустить бота\n"
                "`!shutdown` - выключить бота"
            ),
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def bots_status(self, ctx):
        """Показать статус бота (только для владельца)"""
        # Статистика бота
        guilds_count = len(self.bot.guilds)
        users_count = len(self.bot.users)

        # Пинг
        latency = round(self.bot.latency * 1000)

        # Время работы
        uptime = discord.utils.utcnow() - self.bot.start_time

        # Использование памяти
        import psutil
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024  # в MB

        embed = discord.Embed(
            title="🤖 Статус бота",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="🖥️ Серверов", value=guilds_count, inline=True)
        embed.add_field(name="👥 Пользователей", value=users_count, inline=True)
        embed.add_field(name="📡 Пинг", value=f"{latency}ms", inline=True)

        embed.add_field(name="⏰ Время работы", value=str(uptime).split('.')[0], inline=True)
        embed.add_field(name="💾 Память", value=f"{memory_usage:.2f} MB", inline=True)
        embed.add_field(name="📚 Коги", value=len(self.bot.cogs), inline=True)

        # Статус команд
        total_commands = len(self.bot.commands)
        embed.add_field(name="⚙️ Команды", value=total_commands, inline=True)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        """Устанавливает время старта бота"""
        if not hasattr(self.bot, 'start_time'):
            self.bot.start_time = discord.utils.utcnow()



async def setup(bot):
    await bot.add_cog(Shutdown(bot))