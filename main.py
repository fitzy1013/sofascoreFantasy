import math

import requests
import pandas as pd

round_string = "round-of-32"

player_stats_url = "https://www.sofascore.com/api/v1/event/14059358/lineups"
matches_url = f"https://www.sofascore.com/api/v1/unique-tournament/1786/season/75270/events/round/6/slug/{round_string}"
headers = {
    "baggage": "sentry-environment=production,sentry-release=NcET3aAMezMEwK24KeSEy,sentry-public_key=d693747a6bb242d9bb9cf7069fb57988,sentry-trace_id=e014fdd79b610d411545cadc1dbdbd27",
    "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sentry-trace": "e014fdd79b610d411545cadc1dbdbd27-a1103791400c8d74",
    "x-requested-with": "2844f8"
}


def get_teams_return_dict(match_id):
    match_url = f"https://www.sofascore.com/api/v1/event/{match_id}"
    match_response = requests.get(match_url, headers=headers)
    if match_response.status_code != 200:
        raise Exception("Api Not working")
    else:
        match_response_json = match_response.json()
        home_team = match_response_json['event']['homeTeam']['name']
        home_goals = match_response_json['event']['homeScore']['current']
        away_team = match_response_json['event']['awayTeam']['name']
        away_goals = match_response_json['event']['awayScore']['current']

    team_dict = {
        "home": {
            "teamName": home_team,
            "goals": home_goals,
            "players": []
        },
        "away": {
            "teamName": away_team,
            "goals": away_goals,
            "players": []
        }
    }

    return team_dict


def add_cards_to_players(score_dict, match_id, team_string):
    is_home = (team_string == 'home')
    incident_url = f"https://www.sofascore.com/api/v1/event/{match_id}/incidents"
    incident_response = requests.get(incident_url, headers=headers)

    if incident_response.status_code != 200:
        return

    incident_response_json = incident_response.json()
    card_players = {}  # Track players who received cards: {player_name: card_type}

    for incident in incident_response_json.get('incidents', []):
        # Check if incident is for the correct team and is a card event
        if incident.get('isHome') == is_home and incident['incidentClass'] in ("yellow", "red", "yellowRed"):
            player_name = incident.get('player', {}).get('name')
            incident_type = incident['incidentClass']

            if not player_name:
                continue  # Skip if player name is missing

            # Case 1: Player already has a card
            if player_name in card_players:
                prev_card = card_players[player_name]

                # If previous was yellow and new is yellowRed → upgrade to red
                if prev_card == "yellow" and incident_type == "yellowRed":
                    # Remove previous yellow penalty and apply red penalty
                    update_player_score(score_dict, player_name, undo_yellow=True)
                    update_player_score(score_dict, player_name, is_red=True)
                    card_players[player_name] = "red"  # Mark as red

                # If already red, do nothing (no double penalty)
                elif prev_card == "red":
                    continue

            # Case 2: First card for this player
            else:
                if incident_type == "yellow":
                    update_player_score(score_dict, player_name, is_yellow=True)
                    card_players[player_name] = "yellow"
                elif incident_type in ("yellowRed", "red"):
                    update_player_score(score_dict, player_name, is_red=True)
                    card_players[player_name] = "red"


def update_player_score(players_list, player_name, is_yellow=False, is_red=False, undo_yellow=False):
    """
    Updates the player's score in the players list based on card type.
    - is_yellow: Deduct 1 point for yellow.
    - is_red: Deduct 3 points for red.
    - undo_yellow: Remove previous yellow penalty (+1 point).
    """
    for player in players_list:
        if player['name'] == player_name:
            if undo_yellow:
                player['score'] += 1  # Reverse yellow penalty
            if is_yellow:
                player['score'] -= 1  # Apply yellow penalty
            if is_red:
                player['score'] -= 3  # Apply red penalty
            break


def convert_player_stats_to_score(player, goals_conceeded):
    score = 0
    player_position = player['position']
    player_stats = player['statistics']
    if player_stats:
        score += 1  # point for playing minutes
        if player_stats['minutesPlayed'] >= 60:  # 1 point for playing over 60 minutes
            score += 1
            if goals_conceeded == 0:
                if player_position == 'G':
                    score += 5
                elif player_position == 'D':
                    score += 4
                elif player_position == 'M':
                    score += 1
            if player_position == 'G' or player_position == 'D':
                score -= math.floor(goals_conceeded * 0.5)
        if 'penaltyMiss' in player_stats and player_stats['penaltyMiss'] > 0:
            score -= player_stats['penaltyMiss'] * -2
        if 'goals' in player_stats and player_stats['goals'] > 0:
            if player_position == 'G':
                score += player_stats['goals'] * 10
            if player_position == 'D':
                score += player_stats['goals'] * 6
            if player_position == 'M':
                score += player_stats['goals'] * 5
            if player_position == 'F':
                score += player_stats['goals'] * 4
        if 'penaltyWon' in player_stats and player_stats['penaltyWon'] > 0:
            score += player_stats['penaltyWon']
        if 'goalAssist' in player_stats and player_stats['goalAssist'] > 0:
            score += player_stats['goalAssist'] * 3
        if 'saves' in player_stats and player_stats['saves'] > 0:
            score += math.floor(player_stats['saves'] * 0.5)
        if 'penaltyConceded' in player_stats and player_stats['penaltyConceded'] > 0:
            score += player_stats['penaltyConceded'] * -1
        if 'penaltySave' in player_stats and player_stats['penaltySave'] > 0:
            score += player_stats['penaltySave'] * 5
        clearances, blocks, interceptions = 0, 0, 0
        if 'totalClearance' in player_stats and player_stats['totalClearance'] > 0:
            clearances += player_stats['totalClearance']
        if 'blockedScoringAttempt' in player_stats and player_stats['blockedScoringAttempt'] > 0:
            blocks += player_stats['blockedScoringAttempt']
        if 'interceptionWon' in player_stats and player_stats['interceptionWon'] > 0:
            interceptions += player_stats['interceptionWon']
        total_cbi = clearances + blocks + interceptions
        if player_position == 'G' or player_position == 'F':
            score += math.floor(total_cbi * 1 / 3)
        if player_position == 'D':
            score += math.floor(total_cbi * 1 / 5)
        if player_position == 'M':
            score += math.floor(total_cbi * 1 / 5)
        if 'duelWon' in player_stats and player_stats['duelWon'] > 0:
            score += math.floor(player_stats['duelWon'] * 1 / 5)
        if 'onTargetScoringAttempt' in player_stats and player_stats['onTargetScoringAttempt'] > 0:
            score += math.floor(player_stats['onTargetScoringAttempt'] * 1 / 2)
        if 'keyPass' in player_stats and player_stats['keyPass'] > 0:
            score += math.floor(player_stats['keyPass'] * 1 / 2)

    return score


def get_player_fantasy_scores_from_match_print_to_csv(match_id, teams_dict):
    home_goals, away_goals = teams_dict['home']['goals'], teams_dict['away']['goals']
    stats_url = f"https://www.sofascore.com/api/v1/event/{match_id}/lineups"
    stats_response = requests.get(stats_url, headers=headers)
    if stats_response.status_code != 200:
        return 0
    else:
        stats_response_json = stats_response.json()
        team_string = ['home', 'away']
        for team in team_string:
            for player in stats_response_json[team]['players']:
                score = convert_player_stats_to_score(player, away_goals)
                name = player['player']['name']
                player_score_dict = {
                    "name": name,
                    "score": score
                }
                teams_dict[team]['players'].append(player_score_dict)
            add_cards_to_players(teams_dict[team]['players'], match_id, team)

    return teams_dict


def display_match_data(match_data):
    # Create DataFrames for each team
    home_df = pd.DataFrame(match_data['home']['players'])
    away_df = pd.DataFrame(match_data['away']['players'])

    # Add team name columns
    home_df['Team'] = match_data['home']['teamName']
    away_df['Team'] = match_data['away']['teamName']

    # Sort by score (descending)
    home_df = home_df.sort_values('score', ascending=False)
    away_df = away_df.sort_values('score', ascending=False)

    # Display match summary
    print(f"\n\033[1mMATCH SUMMARY\033[0m")
    print(
        f"{match_data['home']['teamName']} {match_data['home']['goals']} - {match_data['away']['goals']} {match_data['away']['teamName']}\n")

    # Display home team
    print(f"\033[1m{match_data['home']['teamName']} (Home)\033[0m")
    print(home_df[['name', 'score']].rename(columns={'name': 'Player', 'score': 'Score'})
          .to_string(index=False, justify='left'))

    # Display away team
    print(f"\n\033[1m{match_data['away']['teamName']} (Away)\033[0m")
    print(away_df[['name', 'score']].rename(columns={'name': 'Player', 'score': 'Score'})
          .to_string(index=False, justify='left'))


# Note: The original JavaScript code uses HEAD method, but you probably want GET to see the response content
""" 
player_url = f"https://www.sofascore.com/api/v1/search/Adam_Taggert"
player_response = requests.get(player_url, headers=headers)
player_response_json = player_response.json()
"""

"""
match_response = requests.get(matches_url, headers=headers)
match_response_json = match_response.json()
for event in match_response_json['events']:
    event_id = event['id']
    player_stats_url = f"https://www.sofascore.com/api/v1/event/{event_id}/lineups"
    player_stats_response = requests.get(player_stats_url, headers=headers)
    if player_stats_response.status_code == 200:
        player_stats_response_json = player_stats_response.json()
        players_home = player_stats_response_json['home']['players']
        players_away = player_stats_response_json['away']['players']
        print("Home Lineup")
        get_and_print_lineups(players_home)
        print("Away Lineup")
        get_and_print_lineups(players_away)
    else:
        print("No Lineups Available")
"""


def main():
    match_id = 14059359
    team_dict = get_teams_return_dict(match_id)
    display_match_data(get_player_fantasy_scores_from_match_print_to_csv(match_id, team_dict))


if __name__ == "__main__":
    main()
