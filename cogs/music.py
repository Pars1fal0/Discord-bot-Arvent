# music_cog.py
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

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


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Воспроизводит аудио из YouTube")
    @app_commands.describe(url="Ссылка на YouTube видео")
    async def play(self, interaction: discord.Interaction, url: str):
        """Воспроизводит аудио из YouTube"""
        await interaction.response.defer()

        try:
            if not interaction.user.voice:
                await interaction.followup.send("❌ Зайди в голосовой канал сначала!")
                return

            channel = interaction.user.voice.channel
            voice_client = interaction.guild.voice_client

            if voice_client is not None:
                await voice_client.move_to(channel)
            else:
                voice_client = await channel.connect()

            async with interaction.channel.typing():
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                voice_client.play(player, after=lambda e: print(f'Ошибка: {e}') if e else None)

            await interaction.followup.send(f'🎵 Сейчас играет: **{player.title}**')

        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {str(e)}")

    @app_commands.command(name="leave", description="Покидает голосовой канал")
    async def leave(self, interaction: discord.Interaction):
        """Покидает голосовой канал"""
        voice_client = interaction.guild.voice_client
        if voice_client:
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

    @app_commands.command(name="stop", description="Останавливает воспроизведение")
    async def stop(self, interaction: discord.Interaction):
        """Остановить воспроизведение"""
        voice_client = interaction.guild.voice_client
        if voice_client:
            voice_client.stop()
            await interaction.response.send_message("⏹️ Остановлено")


async def setup(bot):
    await bot.add_cog(MusicCog(bot))