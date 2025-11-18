import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from typing import List, Dict, Optional
import math


class TournamentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tournaments = {}
        self.tournament_matches = {}

    @app_commands.command(name="create_tournament", description="Создать новый турнир")
    @app_commands.describe(
        max_participants="Максимальное количество участников",
        name="Название турнира",
        description="Описание турнира"
    )
    async def create_tournament(self, interaction: discord.Interaction, max_participants: int, name: str, description: str = ""):
        """Создать новый турнир"""
        try:
            if name in self.active_tournaments:
                await interaction.response.send_message("❌ Турнир с таким названием уже существует!", ephemeral=True)
                return

            if max_participants < 2:
                await interaction.response.send_message("❌ Минимальное количество участников - 2!", ephemeral=True)
                return

            tournament = {
                "name": name,
                "description": description,
                "max_participants": max_participants,
                "participants": [],
                "status": "registration",
                "creator": interaction.user.id,
                "current_round": 0,
                "channel_id": interaction.channel.id
            }

            self.active_tournaments[name] = tournament
            self.tournament_matches[name] = {}

            embed = discord.Embed(
                title=f"🎯 Турнир: {name}",
                description=description,
                color=discord.Color.green()
            )
            embed.add_field(name="Макс. участников", value=max_participants, inline=True)
            embed.add_field(name="Статус", value="Регистрация открыта", inline=True)
            embed.add_field(name="Участников", value="0", inline=True)
            embed.add_field(name="Создатель", value=interaction.user.display_name, inline=True)
            embed.set_footer(text="Используйте /join чтобы присоединиться")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка при создании турнира: {str(e)}", ephemeral=True)

    @app_commands.command(name="join_tournament", description="Присоединиться к турниру")
    @app_commands.describe(tournament_name="Название турнира")
    async def join_tournament(self, interaction: discord.Interaction, tournament_name: str):
        """Присоединиться к турниру"""
        if tournament_name not in self.active_tournaments:
            await interaction.response.send_message("❌ Турнир не найден! Используйте /tournaments чтобы посмотреть список турниров.", ephemeral=True)
            return

        tournament = self.active_tournaments[tournament_name]

        if tournament["status"] != "registration":
            await interaction.response.send_message("❌ Регистрация на турнир закрыта!", ephemeral=True)
            return

        if interaction.user.id in [p["id"] for p in tournament["participants"]]:
            await interaction.response.send_message("❌ Вы уже зарегистрированы в этом турнире!", ephemeral=True)
            return

        if len(tournament["participants"]) >= tournament["max_participants"]:
            await interaction.response.send_message("❌ Турнир уже заполнен!", ephemeral=True)
            return

        participant = {
            "id": interaction.user.id,
            "name": interaction.user.display_name,
            "wins": 0,
            "losses": 0
        }

        tournament["participants"].append(participant)

        embed = discord.Embed(
            title="✅ Успешная регистрация",
            description=f"**{interaction.user.display_name}** присоединился к турниру **{tournament_name}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Участников", value=f"{len(tournament['participants'])}/{tournament['max_participants']}",
                        inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="start_tournament", description="Начать турнир")
    @app_commands.describe(tournament_name="Название турнира")
    async def start_tournament(self, interaction: discord.Interaction, tournament_name: str):
        """Начать турнир"""
        if tournament_name not in self.active_tournaments:
            await interaction.response.send_message("❌ Турнир не найден!", ephemeral=True)
            return

        tournament = self.active_tournaments[tournament_name]

        if tournament["creator"] != interaction.user.id:
            await interaction.response.send_message("❌ Только создатель турнира может его запустить!", ephemeral=True)
            return

        if tournament["status"] != "registration":
            await interaction.response.send_message("❌ Турнир уже запущен или завершен!", ephemeral=True)
            return

        participants_count = len(tournament["participants"])
        if participants_count < 2:
            await interaction.response.send_message("❌ Недостаточно участников для начала турнира!", ephemeral=True)
            return

        # Перемешиваем участников
        random.shuffle(tournament["participants"])
        tournament["status"] = "active"
        tournament["current_round"] = 1

        # Создаем турнирную сетку
        bracket = self.generate_bracket(tournament["participants"])
        self.tournament_matches[tournament_name] = bracket

        embed = discord.Embed(
            title=f"🎯 Турнир {tournament_name} начался!",
            description="Турнирная сетка создана",
            color=discord.Color.gold()
        )
        embed.add_field(name="Участников", value=participants_count, inline=True)
        embed.add_field(name="Текущий раунд", value="1", inline=True)

        await interaction.response.send_message(embed=embed)
        await self.send_bracket(interaction, tournament_name)

    def generate_bracket(self, participants: List[Dict]) -> Dict:
        """Генерация турнирной сетки"""
        bracket = {}
        round_num = 1
        current_matches = []

        # Создаем первый раунд
        for i in range(0, len(participants), 2):
            if i + 1 < len(participants):
                match = {
                    "round": round_num,
                    "player1": participants[i],
                    "player2": participants[i + 1],
                    "winner": None,
                    "completed": False
                }
            else:
                # Если нечетное количество участников, один проходит автоматически
                match = {
                    "round": round_num,
                    "player1": participants[i],
                    "player2": None,
                    "winner": participants[i],
                    "completed": True
                }
            current_matches.append(match)

        bracket[round_num] = current_matches

        # Создаем последующие раунды
        while len(current_matches) > 1:
            round_num += 1
            next_round_matches = []

            for i in range(0, len(current_matches), 2):
                if i + 1 < len(current_matches):
                    match = {
                        "round": round_num,
                        "player1": None,
                        "player2": None,
                        "winner": None,
                        "completed": False
                    }
                else:
                    match = {
                        "round": round_num,
                        "player1": None,
                        "player2": None,
                        "winner": None,
                        "completed": False
                    }
                next_round_matches.append(match)

            bracket[round_num] = next_round_matches
            current_matches = next_round_matches

        return bracket

    async def send_bracket(self, interaction: discord.Interaction, tournament_name: str):
        """Отправка турнирной сетки"""
        bracket = self.tournament_matches[tournament_name]

        embed = discord.Embed(
            title=f"🏆 Турнирная сетка: {tournament_name}",
            color=discord.Color.purple()
        )

        for round_num, matches in bracket.items():
            round_text = ""
            for i, match in enumerate(matches):
                player1_name = match["player1"]["name"] if match["player1"] else "???"
                player2_name = match["player2"]["name"] if match["player2"] else "???"

                if match["winner"]:
                    winner_indicator = " 👑" if match["winner"]["id"] == match["player1"]["id"] else " 👑" if \
                    match["winner"]["id"] == match["player2"]["id"] else ""
                    round_text += f"**Матч {i + 1}:** {player1_name} vs {player2_name}{winner_indicator}\n"
                else:
                    round_text += f"**Матч {i + 1}:** {player1_name} vs {player2_name}\n"

            embed.add_field(
                name=f"Раунд {round_num}",
                value=round_text or "Нет матчей",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="report_score", description="Сообщить результат матча")
    @app_commands.describe(
        tournament_name="Название турнира",
        round_number="Номер раунда",
        match_number="Номер матча",
        winner_number="Номер победителя (1 или 2)"
    )
    async def report_score(self, interaction: discord.Interaction, tournament_name: str, round_number: int, match_number: int, winner_number: int):
        """Сообщить результат матча"""
        if tournament_name not in self.active_tournaments:
            await interaction.response.send_message("❌ Турнир не найден!", ephemeral=True)
            return

        tournament = self.active_tournaments[tournament_name]
        bracket = self.tournament_matches[tournament_name]

        if round_number not in bracket or match_number - 1 >= len(bracket[round_number]):
            await interaction.response.send_message("❌ Матч не найден!", ephemeral=True)
            return

        match = bracket[round_number][match_number - 1]

        # Проверяем, является ли пользователь участником матча
        user_id = interaction.user.id
        is_player1 = match["player1"] and match["player1"]["id"] == user_id
        is_player2 = match["player2"] and match["player2"]["id"] == user_id

        if not (is_player1 or is_player2) and tournament["creator"] != user_id:
            await interaction.response.send_message("❌ Вы не можете сообщать результат этого матча!", ephemeral=True)
            return

        if match["completed"]:
            await interaction.response.send_message("❌ Результат этого матча уже зафиксирован!", ephemeral=True)
            return

        if winner_number not in [1, 2]:
            await interaction.response.send_message("❌ Номер победителя должен быть 1 или 2!", ephemeral=True)
            return

        # Определяем победителя
        if winner_number == 1:
            if not match["player1"]:
                await interaction.response.send_message("❌ В этом матче нет первого игрока!", ephemeral=True)
                return
            match["winner"] = match["player1"]
        else:
            if not match["player2"]:
                await interaction.response.send_message("❌ В этом матче нет второго игрока!", ephemeral=True)
                return
            match["winner"] = match["player2"]

        match["completed"] = True

        # Обновляем статистику игроков
        winner = match["winner"]
        loser = match["player1"] if winner["id"] != match["player1"]["id"] else match["player2"]

        for participant in tournament["participants"]:
            if participant["id"] == winner["id"]:
                participant["wins"] += 1
            elif loser and participant["id"] == loser["id"]:
                participant["losses"] += 1

        # Обновляем следующий раунд
        await self.update_next_round(tournament_name, round_number, match_number, winner)

        embed = discord.Embed(
            title="✅ Результат зафиксирован",
            description=f"Победитель матча: **{winner['name']}**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)
        await self.send_bracket(interaction, tournament_name)

    async def update_next_round(self, tournament_name: str, current_round: int, match_number: int, winner: Dict):
        """Обновление следующего раунда турнира"""
        bracket = self.tournament_matches[tournament_name]
        next_round = current_round + 1

        if next_round not in bracket:
            return

        next_match_index = (match_number - 1) // 2
        if next_match_index >= len(bracket[next_round]):
            return

        next_match = bracket[next_round][next_match_index]

        # Определяем позицию в следующем матче
        position = (match_number - 1) % 2  # 0 для player1, 1 для player2

        if position == 0:
            next_match["player1"] = winner
        else:
            next_match["player2"] = winner

    @app_commands.command(name="tournament_info", description="Информация о турнире")
    @app_commands.describe(tournament_name="Название турнира")
    async def tournament_info(self, interaction: discord.Interaction, tournament_name: str):
        """Информация о турнире"""
        if tournament_name not in self.active_tournaments:
            await interaction.response.send_message("❌ Турнир не найден!", ephemeral=True)
            return

        tournament = self.active_tournaments[tournament_name]

        embed = discord.Embed(
            title=f"🎯 Турнир: {tournament_name}",
            description=tournament["description"],
            color=discord.Color.blue()
        )

        status_text = {
            "registration": "📝 Регистрация",
            "active": "⚡ Активен",
            "finished": "🏁 Завершен"
        }[tournament["status"]]

        embed.add_field(name="Статус", value=status_text, inline=True)
        embed.add_field(name="Участников", value=f"{len(tournament['participants'])}/{tournament['max_participants']}",
                        inline=True)
        embed.add_field(name="Текущий раунд", value=tournament["current_round"], inline=True)

        # Список участников
        participants_text = "\n".join(
            [f"• {p['name']} (побед: {p['wins']}, поражений: {p['losses']})" for p in tournament["participants"]])
        if participants_text:
            embed.add_field(name="Участники", value=participants_text[:1024], inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="end_tournament", description="Завершить турнир")
    @app_commands.describe(tournament_name="Название турнира")
    async def end_tournament(self, interaction: discord.Interaction, tournament_name: str):
        """Завершить турнир"""
        if tournament_name not in self.active_tournaments:
            await interaction.response.send_message("❌ Турнир не найден!", ephemeral=True)
            return

        tournament = self.active_tournaments[tournament_name]

        if tournament["creator"] != interaction.user.id:
            await interaction.response.send_message("❌ Только создатель турнира может его завершить!", ephemeral=True)
            return

        tournament["status"] = "finished"

        # Определяем победителя
        bracket = self.tournament_matches[tournament_name]
        final_round = max(bracket.keys()) if bracket else 0
        final_match = bracket[final_round][0] if final_round > 0 and bracket.get(final_round) else None

        winner = final_match["winner"] if final_match and final_match.get("completed") else None

        embed = discord.Embed(
            title=f"🏁 Турнир {tournament_name} завершен!",
            color=discord.Color.gold()
        )

        if winner:
            embed.add_field(name="🏆 Победитель", value=winner["name"], inline=False)
            embed.add_field(name="Побед/Поражений", value=f"{winner['wins']}-{winner['losses']}", inline=True)
        else:
            embed.add_field(name="Победитель", value="Не определен", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="list_tournaments", description="Список активных турниров")
    async def list_tournaments(self, interaction: discord.Interaction):
        """Список активных турниров"""
        if not self.active_tournaments:
            await interaction.response.send_message("❌ Нет активных турниров!", ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 Активные турниры",
            color=discord.Color.blue()
        )

        for name, tournament in self.active_tournaments.items():
            status_text = {
                "registration": "Регистрация",
                "active": "Активен",
                "finished": "Завершен"
            }[tournament["status"]]

            embed.add_field(
                name=name,
                value=f"Статус: {status_text}\nУчастников: {len(tournament['participants'])}/{tournament['max_participants']}",
                inline=True
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leave_tournament", description="Покинуть турнир")
    @app_commands.describe(tournament_name="Название турнира")
    async def leave_tournament(self, interaction: discord.Interaction, tournament_name: str):
        """Покинуть турнир"""
        if tournament_name not in self.active_tournaments:
            await interaction.response.send_message("❌ Турнир не найден!", ephemeral=True)
            return

        tournament = self.active_tournaments[tournament_name]

        if tournament["status"] != "registration":
            await interaction.response.send_message("❌ Нельзя покинуть турнир после начала!", ephemeral=True)
            return

        participant_index = None
        for i, participant in enumerate(tournament["participants"]):
            if participant["id"] == interaction.user.id:
                participant_index = i
                break

        if participant_index is None:
            await interaction.response.send_message("❌ Вы не зарегистрированы в этом турнире!", ephemeral=True)
            return

        tournament["participants"].pop(participant_index)
        await interaction.response.send_message(f"✅ Вы покинули турнир **{tournament_name}**")

    @app_commands.command(name="show_bracket", description="Показать турнирную сетку")
    @app_commands.describe(tournament_name="Название турнира")
    async def show_bracket(self, interaction: discord.Interaction, tournament_name: str):
        """Показать турнирную сетку"""
        if tournament_name not in self.active_tournaments:
            await interaction.response.send_message("❌ Турнир не найден!", ephemeral=True)
            return

        await self.send_bracket(interaction, tournament_name)

async def setup(bot):
    await bot.add_cog(TournamentCog(bot))