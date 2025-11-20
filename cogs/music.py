# music_cog.py
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from collections import deque
import math

# Настройки для yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class Song:
    def __init__(self, data, requester):
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')
        self.requester = requester

    def get_embed(self):
        embed = discord.Embed(title=self.title, color=0x00ff00)
        embed.add_field(name="Длительность",
                        value=f"{self.duration // 60}:{self.duration % 60:02d}" if self.duration else "Неизвестно",
                        inline=True)
        embed.add_field(name="Добавил", value=self.requester.mention, inline=True)
        if self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail)
        return embed


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]

    async def play_next(self, interaction):
        queue = self.get_queue(interaction.guild.id)
        if queue:
            song = queue.popleft()
            voice_client = interaction.guild.voice_client

            try:
                player = await YTDLSource.from_url(song.url, loop=self.bot.loop, stream=True)
                voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction),
                                                                                           self.bot.loop))

                embed = discord.Embed(title="🎵 Сейчас играет", color=0x00ff00)
                embed.add_field(name="Трек", value=song.title, inline=False)
                embed.add_field(name="Длительность",
                                value=f"{song.duration // 60}:{song.duration % 60:02d}" if song.duration else "Неизвестно",
                                inline=True)
                embed.add_field(name="Добавил", value=song.requester.mention, inline=True)
                await interaction.channel.send(embed=embed)
            except Exception as e:
                await interaction.channel.send(f"❌ Ошибка воспроизведения: {str(e)}")
                await self.play_next(interaction)
        else:
            # Если очередь пуста, отключаемся через 1 минуту
            await asyncio.sleep(60)
            voice_client = interaction.guild.voice_client
            if voice_client and not voice_client.is_playing():
                await voice_client.disconnect()
                await interaction.channel.send("👋 Очередь пуста, отключаюсь")

    @app_commands.command(name="play", description="Добавляет трек в очередь")
    @app_commands.describe(url="Ссылка на YouTube видео или название для поиска")
    async def play(self, interaction: discord.Interaction, url: str):
        """Добавляет трек в очередь"""
        await interaction.response.defer()

        try:
            if not interaction.user.voice:
                await interaction.followup.send("❌ Зайди в голосовой канал сначала!")
                return

            channel = interaction.user.voice.channel
            voice_client = interaction.guild.voice_client

            if voice_client is not None:
                if voice_client.channel != channel:
                    await voice_client.move_to(channel)
            else:
                voice_client = await channel.connect()

            # Получаем информацию о треке
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if 'entries' in data:
                data = data['entries'][0]

            song = Song(data, interaction.user)
            queue = self.get_queue(interaction.guild.id)
            queue.append(song)

            # Если ничего не играет, начинаем воспроизведение
            if not voice_client.is_playing():
                await self.play_next(interaction)
                await interaction.followup.send(f"✅ Добавлено в очередь: **{song.title}**")
            else:
                await interaction.followup.send(f"✅ Добавлено в очередь: **{song.title}** (Позиция: {len(queue)})")

        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {str(e)}")

    @app_commands.command(name="skip", description="Пропускает текущий трек")
    async def skip(self, interaction: discord.Interaction):
        """Пропускает текущий трек"""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("⏭️ Трек пропущен")
        else:
            await interaction.response.send_message("❌ Сейчас ничего не играет")

    @app_commands.command(name="queue", description="Показывает текущую очередь")
    async def queue(self, interaction: discord.Interaction):
        """Показывает текущую очередь"""
        queue = self.get_queue(interaction.guild.id)
        if not queue:
            await interaction.response.send_message("📪 Очередь пуста")
            return

        embed = discord.Embed(title="🎵 Очередь воспроизведения", color=0x00ff00)

        # Текущий играющий трек (если есть)
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            embed.add_field(name="Сейчас играет", value="*Информация о текущем треке*", inline=False)

        # Следующие 10 треков в очереди
        for i, song in enumerate(list(queue)[:10]):
            duration = f"{song.duration // 60}:{song.duration % 60:02d}" if song.duration else "Неизвестно"
            embed.add_field(
                name=f"{i + 1}. {song.title}",
                value=f"Длительность: {duration} | Добавил: {song.requester.mention}",
                inline=False
            )

        if len(queue) > 10:
            embed.set_footer(text=f"И еще {len(queue) - 10} треков в очереди...")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Показывает текущий играющий трек")
    async def nowplaying(self, interaction: discord.Interaction):
        """Показывает текущий играющий трек"""
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("❌ Сейчас ничего не играет")
            return

        # К сожалению, мы не храним информацию о текущем треке,
        # но можно добавить это в будущем
        await interaction.response.send_message("🎵 Сейчас играет трек (информация о текущем треке)")

    @app_commands.command(name="clear", description="Очищает очередь")
    async def clear(self, interaction: discord.Interaction):
        """Очищает очередь"""
        queue = self.get_queue(interaction.guild.id)
        queue.clear()
        await interaction.response.send_message("🗑️ Очередь очищена")

    @app_commands.command(name="leave", description="Покидает голосовой канал и очищает очередь")
    async def leave(self, interaction: discord.Interaction):
        """Покидает голосовой канал"""
        voice_client = interaction.guild.voice_client
        if voice_client:
            # Очищаем очередь
            if interaction.guild.id in self.queues:
                self.queues[interaction.guild.id].clear()
            await voice_client.disconnect()
            await interaction.response.send_message("👋 Отключился от канала")
        else:
            await interaction.response.send_message("❌ Я не в голосовом канале")

    @app_commands.command(name="pause", description="Ставит воспроизведение на паузу")
    async def pause(self, interaction: discord.Interaction):
        """Пауза"""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Пауза")
        else:
            await interaction.response.send_message("❌ Нечего ставить на паузу")

    @app_commands.command(name="resume", description="Продолжает воспроизведение")
    async def resume(self, interaction: discord.Interaction):
        """Продолжить воспроизведение"""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Продолжаем")
        else:
            await interaction.response.send_message("❌ Нечего продолжать")

    @app_commands.command(name="stop", description="Останавливает воспроизведение и очищает очередь")
    async def stop(self, interaction: discord.Interaction):
        """Остановить воспроизведение"""
        voice_client = interaction.guild.voice_client
        if voice_client:
            voice_client.stop()
            # Очищаем очередь
            if interaction.guild.id in self.queues:
                self.queues[interaction.guild.id].clear()
            await interaction.response.send_message("⏹️ Воспроизведение остановлено и очередь очищена")


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


async def setup(bot):
    await bot.add_cog(MusicCog(bot))