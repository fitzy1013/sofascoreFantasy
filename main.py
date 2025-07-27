import math

import requests
import pandas as pd

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


import math


def convert_player_stats_to_score(player, goals_conceded, player_name, penalty_list):
    if not player.get('statistics'):
        return 0

    position = player['position']
    stats = player['statistics']
    score = 0

    # Base points for playing
    score += 1  # point for playing minutes
    if stats['minutesPlayed'] >= 60:
        score += 1  # point for playing over 60 minutes
        score += _calculate_defensive_bonus(position, goals_conceded)

    # Goal-related points
    score += _calculate_goal_points(position, stats, player_name, penalty_list)

    # Penalty-related points
    score += _calculate_penalty_points(stats)

    # Assist and passing points
    score += _calculate_assist_and_passing_points(stats)

    # Defensive actions points
    score += _calculate_defensive_action_points(position, stats)

    # Other miscellaneous points
    score += _calculate_miscellaneous_points(stats)

    return score


def _calculate_defensive_bonus(position, goals_conceeded):
    if goals_conceeded == 0:
        return {
            'G': 5,
            'D': 4,
            'M': 1,
        }.get(position, 0)

    if position in ('G', 'D'):
        return -math.floor(goals_conceeded * 0.5)
    return 0


def _calculate_goal_points(position, stats, player_name, penalty_list):
    if 'goals' not in stats or stats['goals'] <= 0:
        return 0

    goal_multipliers = {
        'G': 10,
        'D': 6,
        'M': 5,
        'F': 4,
    }

    reg_goals = stats['goals']
    pen_goals = 0

    for pen in penalty_list:
        if pen['player']['name'] == player_name:
            reg_goals -= 1
            pen_goals += 1

    return reg_goals * goal_multipliers.get(position, 0) + (pen_goals * 3)


def _calculate_penalty_points(stats):
    points = 0
    if stats.get('penaltyMiss', 0) > 0:
        points -= stats['penaltyMiss'] * 2
    if stats.get('penaltyConceded', 0) > 0:
        points -= stats['penaltyConceded']
    if stats.get('penaltySave', 0) > 0:
        points += stats['penaltySave'] * 5
    if stats.get('penaltyWon', 0) > 0:
        points += stats['penaltyWon']
    return points


def _calculate_assist_and_passing_points(stats):
    points = 0
    if stats.get('goalAssist', 0) > 0:
        points += stats['goalAssist'] * 3
    if stats.get('keyPass', 0) > 0:
        points += math.floor(stats['keyPass'] * 0.5)
    return points


def _calculate_defensive_action_points(position, stats):
    points = 0

    # Saves (mainly for goalkeepers)
    if stats.get('saves', 0) > 0:
        points += math.floor(stats['saves'] * 0.5)

    # Clearances, blocks, interceptions
    clearances = stats.get('totalClearance', 0)
    blocks = stats.get('blockedScoringAttempt', 0)
    interceptions = stats.get('interceptionWon', 0)
    total_cbi = clearances + blocks + interceptions

    if total_cbi > 0:
        cbi_multiplier = {
            'G': 1 / 3,
            'F': 1 / 3,
            'D': 1 / 5,
            'M': 1 / 5,
        }.get(position, 0)
        points += math.floor(total_cbi * cbi_multiplier)

    return points


def _calculate_miscellaneous_points(stats):
    points = 0
    if stats.get('duelWon', 0) > 0:
        points += math.floor(stats['duelWon'] * 0.2)
    if stats.get('onTargetScoringAttempt', 0) > 0:
        points += math.floor(stats['onTargetScoringAttempt'] * 0.5)
    return points


def get_player_fantasy_scores_from_match_print_to_csv(match_id, teams_dict, penalty_list):
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
                goals = 0
                if team == 'home':
                    goals = away_goals
                else:
                    goals = home_goals
                name = player['player']['name']
                score = convert_player_stats_to_score(player, goals, name, penalty_list)
                player_score_dict = {
                    "name": name,
                    "score": score
                }
                teams_dict[team]['players'].append(player_score_dict)
            add_cards_to_players(teams_dict[team]['players'], match_id, team)

    return teams_dict


def get_list_of_pens(match_id):
    incident_url = f"https://www.sofascore.com/api/v1/event/{match_id}/incidents"
    incident_response = requests.get(incident_url, headers=headers)

    if incident_response.status_code != 200:
        return

    incident_response_json = incident_response.json()
    penalty_list = []
    for incident in incident_response_json['incidents']:
        if 'incidentClass' in incident and incident['incidentClass'] == "penalty":
            penalty_list.append(incident)

    return penalty_list


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


def main():
    match_id = 14059359
    penalty_list = get_list_of_pens(match_id)
    team_dict = get_teams_return_dict(match_id)
    display_match_data(get_player_fantasy_scores_from_match_print_to_csv(match_id, team_dict, penalty_list))


if __name__ == "__main__":
    main()
