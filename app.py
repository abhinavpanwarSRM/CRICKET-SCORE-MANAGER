# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import random
import time
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "cricket_secret"
app.config['SESSION_TYPE'] = 'filesystem'

# Add session support
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def index():
    return render_template('main.html', page="home")

@app.route('/add_players', methods=['GET', 'POST'])
def add_players():
    if request.method == 'POST':
        team1_name = request.form['team1_name']
        team2_name = request.form['team2_name']
        
        # Get all players from both teams, filtering out empty entries
        team1 = [p.strip() for p in request.form.getlist('team1') if p.strip()]
        team2 = [p.strip() for p in request.form.getlist('team2') if p.strip()]
        
        # Validate at least 2 players per team
        if len(team1) < 2:
            return render_template('main.html', page="add_players", error="Team 1 needs at least 2 players")
        if len(team2) < 2:
            return render_template('main.html', page="add_players", error="Team 2 needs at least 2 players")
        
        overs = int(request.form['overs'])

        # Clear previous session data
        session.clear()
        
        session['team1_name'] = team1_name
        session['team2_name'] = team2_name
        session['team1'] = team1
        session['team2'] = team2
        session['overs'] = overs
        return redirect(url_for('toss_page'))
    
    return render_template('main.html', page="add_players")

@app.route('/toss')
def toss_page():
    return render_template('main.html', page="toss")

@app.route('/perform_toss')
def perform_toss():
    teams = [session['team1_name'], session['team2_name']]
    toss_winner = random.choice(teams)
    toss_loser = session['team1_name'] if toss_winner == session['team2_name'] else session['team2_name']
    
    session['toss_winner'] = toss_winner
    session['toss_loser'] = toss_loser
    
    return jsonify({
        'winner': toss_winner,
        'loser': toss_loser
    })

@app.route('/toss_decision', methods=['POST'])
def toss_decision():
    choice = request.form['choice']
    session['batting_team'] = session['toss_winner'] if choice == "bat" else session['toss_loser']
    session['bowling_team'] = session['toss_loser'] if choice == "bat" else session['toss_winner']
    
    # Initialize score variables for first innings
    session['innings'] = 1
    session['current_over'] = 0
    session['current_ball'] = 0
    session['total_runs'] = 0
    session['wickets'] = 0
    session['score'] = []
    session['batsmen'] = []
    session['striker_index'] = 0
    session['non_striker_index'] = 1
    session['bowlers'] = []
    session['current_bowler'] = None
    session['current_bowler_index'] = -1
    session['previous_bowler'] = None
    session['free_hit'] = False
    session['target'] = None
    session['last_ball_wicket'] = False
    
    return redirect(url_for('select_batsmen'))

@app.route('/select_batsmen', methods=['GET', 'POST'])
def select_batsmen():
    if request.method == 'POST':
        striker = request.form['striker']
        non_striker = request.form['non_striker']
        
        # Initialize batsmen data
        session['batsmen'] = [
            {"name": striker, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False, "wicket_type": None},
            {"name": non_striker, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False, "wicket_type": None}
        ]
        
        return redirect(url_for('select_bowler'))
    
    # Get the batting team's players
    batting_team_players = session['team1'] if session['batting_team'] == session['team1_name'] else session['team2']
    return render_template('main.html', page="select_batsmen", players=batting_team_players)

@app.route('/select_bowler', methods=['GET', 'POST'])
def select_bowler():
    if request.method == 'POST':
        bowler = request.form['bowler']
        
        # Initialize bowler data if not exists
        if 'bowlers' not in session:
            session['bowlers'] = []
        
        # Add bowler if not already added
        bowler_exists = False
        for i, b in enumerate(session['bowlers']):
            if b['name'] == bowler:
                session['current_bowler_index'] = i
                bowler_exists = True
                break
        
        if not bowler_exists:
            session['bowlers'].append({
                "name": bowler,
                "overs": 0,
                "maidens": 0,
                "runs": 0,
                "wickets": 0,
                "balls": 0
            })
            session['current_bowler_index'] = len(session['bowlers']) - 1
        
        session['current_bowler'] = bowler
        # Store the current bowler to prevent selection in next over
        session['previous_bowler'] = bowler
        return redirect(url_for('score'))
    
    # Get the bowling team's players
    bowling_team_players = session['team1'] if session['bowling_team'] == session['team1_name'] else session['team2']
    
    # Filter out the previous bowler if it exists
    available_bowlers = bowling_team_players.copy()
    if 'previous_bowler' in session and session['previous_bowler'] in available_bowlers:
        available_bowlers.remove(session['previous_bowler'])
    
    return render_template('main.html', page="select_bowler", players=available_bowlers)

@app.route('/score', methods=['GET', 'POST'])
def score():
    # Check if we're coming from new batsman after last ball wicket
    if request.method == 'GET' and session.get('last_ball_wicket', False):
        session['last_ball_wicket'] = False
        # If it was the last ball of the over, redirect to bowler selection
        if session['current_ball'] >= 6:
            return redirect(url_for('select_bowler'))
    
    if request.method == 'POST':
        # Get ball outcome
        runs = int(request.form['runs'])
        is_wicket = 'is_wicket' in request.form
        wicket_type = request.form.get('wicket_type', '')
        is_run_out = wicket_type == 'Run Out'
        run_out_batsman = request.form.get('run_out_batsman', '')
        
        # Handle extras
        is_extra = runs < 0
        is_wide = runs == -1
        is_no_ball = runs == -2
        
        # Update ball count (except for wides and no-balls)
        if not (is_wide or is_no_ball):
            session['current_ball'] += 1
        
        # Update bowler stats
        if session['current_bowler_index'] >= 0:
            # Only increment ball count for legitimate deliveries (not wides or no-balls)
            if not (is_wide or is_no_ball):
                session['bowlers'][session['current_bowler_index']]['balls'] += 1
            
            # Add runs to bowler's account
            if is_wide:
                session['bowlers'][session['current_bowler_index']]['runs'] += 1
            elif is_no_ball:
                session['bowlers'][session['current_bowler_index']]['runs'] += 1
            elif runs >= 0:
                session['bowlers'][session['current_bowler_index']]['runs'] += runs
        
        # Update batsman stats if not a wide/no-ball
        if runs >= 0 and not is_extra:
            session['batsmen'][session['striker_index']]['runs'] += runs
            if not is_extra:  # Only count balls for legitimate deliveries
                session['batsmen'][session['striker_index']]['balls'] += 1
            
            if runs == 4:
                session['batsmen'][session['striker_index']]['fours'] += 1
            elif runs == 6:
                session['batsmen'][session['striker_index']]['sixes'] += 1
        
        # Update total runs
        if is_no_ball:
            session['total_runs'] += 1  # Only 1 run for no ball
        elif is_wide:
            session['total_runs'] += 1  # Only 1 run for wide
        else:
            session['total_runs'] += runs
        
        # Handle free hit
        if session.get('free_hit', False):
            # Wicket can only be run out on free hit
            if is_wicket and wicket_type != 'Run Out':
                is_wicket = False
            
            # Reset free hit after this delivery
            session['free_hit'] = False
        
        # Set free hit for next ball if no ball
        if is_no_ball:
            session['free_hit'] = True
        
        # Record ball details BEFORE handling wicket
        ball_data = {
            "over": session['current_over'],
            "ball": session['current_ball'],
            "batsman": session['batsmen'][session['striker_index']]['name'],
            "bowler": session['current_bowler'],
            "runs": runs,
            "is_wicket": is_wicket,
            "wicket_type": wicket_type if is_wicket else None,
            "is_extra": is_extra,
            "extra_type": "WD" if is_wide else "NB" if is_no_ball else None
        }
        session['score'].append(ball_data)
        
        # Handle wicket
        if is_wicket:
            session['wickets'] += 1
            
            # Determine which batsman is out
            if is_run_out and run_out_batsman:
                # Find the run out batsman
                for i, batsman in enumerate(session['batsmen']):
                    if batsman['name'] == run_out_batsman:
                        session['batsmen'][i]['out'] = True
                        session['batsmen'][i]['wicket_type'] = wicket_type
                        break
            else:
                # Regular dismissal
                session['batsmen'][session['striker_index']]['out'] = True
                session['batsmen'][session['striker_index']]['wicket_type'] = wicket_type
            
            # Update bowler wickets (except run outs)
            if session['current_bowler_index'] >= 0 and not is_run_out:
                session['bowlers'][session['current_bowler_index']]['wickets'] += 1
            
            # Handle runout cases - determine who should be on strike
            if is_wicket and is_run_out:
                # Determine which batsman was run out
                run_out_striker = (run_out_batsman == session['batsmen'][session['striker_index']]['name'])
                run_out_non_striker = (run_out_batsman == session['batsmen'][session['non_striker_index']]['name']) if session['non_striker_index'] != -1 else False
                
                # If striker was run out and odd runs were scored, non-striker should stay on strike
                if run_out_striker and runs % 2 == 1:
                    # Non-striker becomes striker, new batsman comes at non-strike
                    session['striker_index'] = session['non_striker_index']
                    session['non_striker_index'] = -1  # Flag for new batsman at non-strike
                
                # If non-striker was run out and even runs were scored, striker should stay on strike
                elif run_out_non_striker and runs % 2 == 0:
                    # Striker stays on strike, new batsman comes at non-strike
                    session['non_striker_index'] = -1  # Flag for new batsman at non-strike
                
                # If non-striker was run out and odd runs were scored, new batsman should come at strike
                elif run_out_non_striker and runs % 2 == 1:
                    # Current striker moves to non-strike, new batsman comes at strike
                    session['non_striker_index'] = session['striker_index']  # Current striker moves to non-strike
                    session['striker_index'] = -1  # Flag for new batsman at strike
                
                # If striker was run out and even runs were scored, new batsman should come at strike
                elif run_out_striker and runs % 2 == 0:
                    # New batsman comes at striker position, non-striker stays
                    session['striker_index'] = -1  # Flag for new batsman at strike

            # Logic for "last man standing"
            batting_team_players = session['team1'] if session['batting_team'] == session['team1_name'] else session['team2']
            total_players = len(batting_team_players)
            
            # If the last batsman gets out, the innings ends
            if session['wickets'] >= total_players:
                session.modified = True
                return redirect(url_for('innings_end'))

            # If a wicket falls and there's only one batsman left
            if total_players - session['wickets'] == 1:
                # The innings does not end. The last batsman is already on the field.
                # If the striker got out (not run-out)
                if not is_run_out:
                    # The non-striker becomes the new striker
                    session['striker_index'], session['non_striker_index'] = session['non_striker_index'], session['striker_index']
                    # There is no non-striker anymore
                    session['non_striker_index'] = -1

                # If a run-out happened and the striker was out, the non-striker becomes the new striker
                elif is_run_out and session['batsmen'][session['striker_index']]['name'] == run_out_batsman:
                    session['striker_index'], session['non_striker_index'] = session['non_striker_index'], session['striker_index']
                    session['non_striker_index'] = -1

                # If a run-out happened and the non-striker was out, the striker stays on strike
                # No change to striker/non-striker indices is needed in this case
                
                # Check if this was the last ball of the over
                if session['current_ball'] >= 6:
                    session['last_ball_wicket'] = True
                
                session.modified = True
                return redirect(url_for('score'))
            
            # If a new batsman needs to come in
            else:
                # Check if this was the last ball of the over
                if session['current_ball'] >= 6:
                    session['last_ball_wicket'] = True
                    batting_team_players = session['team1'] if session['batting_team'] == session['team1_name'] else session['team2'] 
                    wickets_remaining = len(batting_team_players) - session['wickets']
                    if wickets_remaining > 1:
                        session['striker_index'], session['non_striker_index'] = session['non_striker_index'], session['striker_index']
                
                # We need to find the correct striker. If the wicket was a runout
                # and the striker was runout, a new batsman comes in for the striker's slot.
                # If the non-striker was runout, a new batsman comes in for the non-striker slot.
                
                # Redirect to select new batsman
                session.modified = True
                return redirect(url_for('new_batsman'))

        # Check if target achieved in second innings
        if session['innings'] == 2 and session['total_runs'] >= session['target']:
            session.modified = True
            return redirect(url_for('innings_end'))
        
        # Calculate wickets remaining to determine if we should rotate strike
        batting_team_players = session['team1'] if session['batting_team'] == session['team1_name'] else session['team2']
        wickets_remaining = len(batting_team_players) - session['wickets']
        
        # Switch striker for odd runs only if there's more than one batsman remaining
        if wickets_remaining > 1 and runs % 2 == 1 and not is_wide:  # Wides don't change strike
            session['striker_index'], session['non_striker_index'] = session['non_striker_index'], session['striker_index']
        
        # End of over handling
        if session['current_ball'] >= 6:
            # Update bowler overs (convert balls to proper over format)
            if session['current_bowler_index'] >= 0:
                # Calculate proper overs (6 balls = 1 over)
                total_balls = session['bowlers'][session['current_bowler_index']]['overs'] * 6 + session['bowlers'][session['current_bowler_index']]['balls']
                session['bowlers'][session['current_bowler_index']]['overs'] = total_balls // 6
                session['bowlers'][session['current_bowler_index']]['balls'] = total_balls % 6
                
                # Check for maiden over (0 runs in the over from legal deliveries)
                over_runs = 0
                start_idx = max(0, len(session['score']) - 6)
                for ball in session['score'][start_idx:]:
                    if not ball['is_extra']:
                        over_runs += ball['runs']

                if over_runs == 0:
                    session['bowlers'][session['current_bowler_index']]['maidens'] += 1
            
            session['current_over'] += 1
            session['current_ball'] = 0
            
            # Switch striker and non-striker at the end of the over
            if wickets_remaining > 1:
                session['striker_index'], session['non_striker_index'] = session['non_striker_index'], session['striker_index']
            
            # Check if innings is complete (all overs bowled or all out)
            batting_team_players = session['team1'] if session['batting_team'] == session['team1_name'] else session['team2']
            if session['current_over'] >= session['overs'] or session['wickets'] >= len(batting_team_players):
                # Check if target achieved in second innings
                if session['innings'] == 2 and session['total_runs'] >= session['target']:
                    session.modified = True
                    return redirect(url_for('innings_end'))
                else:
                    session.modified = True
                    return redirect(url_for('innings_end'))
            
            # Redirect to select new bowler for the next over
            session.modified = True
            return redirect(url_for('select_bowler'))
        
        session.modified = True
        return redirect(url_for('score'))
    
    # Calculate current run rate
    total_balls = session['current_over'] * 6 + session['current_ball']
    current_run_rate = (session['total_runs'] / total_balls * 6) if total_balls > 0 else 0
    
    # Get the batting team's players for selecting new batsman if needed
    batting_team_players = session['team1'] if session['batting_team'] == session['team1_name'] else session['team2']
    available_batsmen = []
    for player in batting_team_players:
        player_has_batted = False
        for batsman in session['batsmen']:
            if batsman['name'] == player:
                player_has_batted = True
                break
        if not player_has_batted:
            available_batsmen.append(player)
    
    return render_template('main.html', 
                          page="score", 
                          score=session['score'], 
                          batting_team=session['batting_team'],
                          bowling_team=session['bowling_team'],
                          total_runs=session['total_runs'],
                          wickets=session['wickets'],
                          current_over=session['current_over'],
                          current_ball=session['current_ball'],
                          batsmen=session['batsmen'],
                          striker_index=session['striker_index'],
                          non_striker_index=session['non_striker_index'] if 'non_striker_index' in session else -1,
                          current_run_rate=round(current_run_rate, 2),
                          available_batsmen=available_batsmen,
                          bowlers=session.get('bowlers', []),
                          current_bowler=session.get('current_bowler', ''),
                          free_hit=session.get('free_hit', False),
                          innings=session.get('innings', 1),
                          target=session.get('target', 0))

@app.route('/new_batsman', methods=['GET', 'POST'])
def new_batsman():
    # Get the batting team's players
    batting_team_players = session['team1'] if session['batting_team'] == session['team1_name'] else session['team2']
    
    # Filter out batsmen who are already playing or have played
    available_batsmen = []
    for player in batting_team_players:
        if not any(batsman['name'] == player for batsman in session['batsmen']):
            available_batsmen.append(player)
    
    # If no batsmen left, end the innings
    if not available_batsmen:
        return redirect(url_for('innings_end'))
    
    if request.method == 'POST':
        new_batsman = request.form['new_batsman']
        
        # Add new batsman
        session['batsmen'].append({
            "name": new_batsman, 
            "runs": 0, 
            "balls": 0, 
            "fours": 0, 
            "sixes": 0, 
            "out": False,
            "wicket_type": None
        })
        
        # Find which position the new batsman takes based on session flags
        if session.get('striker_index') == -1:
            # New batsman comes at striker position
            session['striker_index'] = len(session['batsmen']) - 1
        elif session.get('non_striker_index') == -1:
            # New batsman comes at non-strike position
            session['non_striker_index'] = len(session['batsmen']) - 1
        else:
            # Default behavior: determine position based on who got out
            current_batsmen = [b for b in session['batsmen'] if not b['out']]
            if len(current_batsmen) == 2:
                # A batsman at the crease got out. We need to find which one
                out_batsman_name = [b for b in session['batsmen'] if b['out']][-1]['name']
                if session['batsmen'][session['striker_index']]['name'] == out_batsman_name:
                    session['striker_index'] = len(session['batsmen']) - 1
                else:
                    session['non_striker_index'] = len(session['batsmen']) - 1
            else: # This case is for the first two batsmen
                session['striker_index'] = len(session['batsmen']) - 1
        
        # If wicket happened on the last ball of the over
        if session.get('last_ball_wicket', False) and session['current_ball'] >= 6:
            session['last_ball_wicket'] = False  # reset flag
            session['current_ball'] = 0
            session['current_over'] += 1
            return redirect(url_for('select_bowler'))
        
        return redirect(url_for('score'))
    
    return render_template('main.html', page="new_batsman", players=available_batsmen)

class PlayerOfTheMatchEngine:
    def __init__(self, match_data):
        self.match_data = match_data
        self.players = self._compile_player_data()
    
    def _compile_player_data(self):
        """Compile all player performances from both innings"""
        players = {}
        
        # Process batting performances from both innings
        for inning in ['first_innings_batsmen', 'second_innings_batsmen']:
            if inning in self.match_data:
                for batsman in self.match_data[inning]:
                    name = batsman['name']
                    if name not in players:
                        players[name] = {
                            'name': name,
                            'runs': 0,
                            'balls': 0,
                            'fours': 0,
                            'sixes': 0,
                            'strike_rate': 0,
                            'wickets': 0,
                            'overs': 0,
                            'maidens': 0,
                            'bowling_runs': 0,
                            'economy': 0,
                            'team': self._get_player_team(name),
                            'impact_score': 0
                        }
                    
                    players[name]['runs'] += batsman['runs']
                    players[name]['balls'] += batsman['balls']
                    players[name]['fours'] += batsman['fours']
                    players[name]['sixes'] += batsman['sixes']
                    
                    # Calculate strike rate
                    if batsman['balls'] > 0:
                        sr = (batsman['runs'] / batsman['balls']) * 100
                        # Weighted average for strike rate
                        if players[name]['strike_rate'] > 0:
                            total_balls = players[name]['balls']
                            players[name]['strike_rate'] = (
                                (players[name]['strike_rate'] * (total_balls - batsman['balls'])) + 
                                (sr * batsman['balls'])
                            ) / total_balls
                        else:
                            players[name]['strike_rate'] = sr
        
        # Process bowling performances from both innings
        for inning in ['first_innings_bowlers', 'second_innings_bowlers']:
            if inning in self.match_data:
                for bowler in self.match_data[inning]:
                    name = bowler['name']
                    if name not in players:
                        players[name] = {
                            'name': name,
                            'runs': 0,
                            'balls': 0,
                            'fours': 0,
                            'sixes': 0,
                            'strike_rate': 0,
                            'wickets': 0,
                            'overs': 0,
                            'maidens': 0,
                            'bowling_runs': 0,
                            'economy': 0,
                            'team': self._get_player_team(name),
                            'impact_score': 0
                        }
                    
                    # Convert overs to balls for calculation
                    bowler_balls = bowler['overs'] * 6 + bowler['balls']
                    players[name]['wickets'] += bowler['wickets']
                    players[name]['maidens'] += bowler['maidens']
                    players[name]['bowling_runs'] += bowler['runs']
                    
                    # Calculate economy rate
                    if bowler_balls > 0:
                        economy = (bowler['runs'] / bowler_balls) * 6
                        # Weighted average for economy
                        total_balls = players[name].get('bowling_balls', 0) + bowler_balls
                        if players[name].get('economy', 0) > 0:
                            players[name]['economy'] = (
                                (players[name]['economy'] * players[name].get('bowling_balls', 0)) + 
                                (economy * bowler_balls)
                            ) / total_balls
                        else:
                            players[name]['economy'] = economy
                        players[name]['bowling_balls'] = total_balls
        
        return players
    
    def _get_player_team(self, player_name):
        """Determine which team a player belongs to"""
        if 'team1' in self.match_data and player_name in self.match_data['team1']:
            return self.match_data['team1_name']
        elif 'team2' in self.match_data and player_name in self.match_data['team2']:
            return self.match_data['team2_name']
        return "Unknown"
    
    def calculate_impact_scores(self):
        """Calculate impact scores optimized for 5-10 over matches"""
        for name, player in self.players.items():
            # Batting impact - more weight for boundaries and SR in short format
            batting_score = (
                player['runs'] * 1.0 +  # Base runs
                player['fours'] * 1.0 +  # Increased boundary bonus
                player['sixes'] * 2.0 +  # Increased six bonus
                (player['strike_rate'] - 120) * 0.7 if player['strike_rate'] > 120 else 0  # Higher SR threshold
            )
            
            # Bowling impact - wickets are extremely valuable in short format
            bowling_score = (
                player['wickets'] * 18.0 +  # High value for wickets
                (25 - player['economy'] * 2.5) if player.get('economy', 0) > 0 else 0 +  # Economy bonus
                player['maidens'] * 8.0  # Maidens are very valuable in short games
            )
            
            # Match situation impact
            winning_team = self.match_data.get('winner', '')
            match_impact = 1.25 if player['team'] == winning_team else 1.0
            
            # Calculate total impact score
            player['impact_score'] = (batting_score + bowling_score) * match_impact
            player['batting_score'] = batting_score
            player['bowling_score'] = bowling_score
    
    def get_player_of_the_match(self):
        """Determine the player of the match"""
        self.calculate_impact_scores()
        
        if not self.players:
            return None
        
        # Find player with highest impact score
        potm = max(self.players.values(), key=lambda x: x['impact_score'])
        
        # Prepare performance summary
        performance_summary = []
        if potm['batting_score'] > 0:
            performance_summary.append(f"{potm['runs']} runs")
        if potm['bowling_score'] > 0:
            performance_summary.append(f"{potm['wickets']} wickets")
        
        return {
            'player': potm['name'],
            'team': potm['team'],
            'impact_score': round(potm['impact_score'], 2),
            'performance': ", ".join(performance_summary),
            'details': {
                'runs': potm['runs'],
                'wickets': potm['wickets']
            }
        }
    
    def get_top_performers(self, count=3):
        """Get top performers of the match"""
        self.calculate_impact_scores()
        
        if not self.players:
            return []
        
        sorted_players = sorted(
            self.players.values(), 
            key=lambda x: x['impact_score'], 
            reverse=True
        )
        
        return sorted_players[:count]

@app.route('/innings_end')
def innings_end():
    # Calculate bowler economy rates and format overs properly
    for bowler in session.get('bowlers', []):
        # Convert balls to proper over format (e.g., 7 balls = 1.1 overs)
        total_balls = bowler['overs'] * 6 + bowler['balls']
        bowler['overs'] = total_balls // 6
        bowler['balls'] = total_balls % 6
        
        if bowler['overs'] > 0 or bowler['balls'] > 0:
            total_balls = bowler['overs'] * 6 + bowler['balls']
            bowler['economy'] = round(bowler['runs'] / (total_balls / 6), 2) if total_balls > 0 else 0
    
    # Store first innings data
    if session['innings'] == 1:
        session['first_innings_total'] = session['total_runs']
        session['first_innings_wickets'] = session['wickets']
        session['first_innings_overs'] = f"{session['current_over']}.{session['current_ball']}"
        session['first_innings_batsmen'] = session['batsmen'].copy()
        session['first_innings_bowlers'] = session['bowlers'].copy()
        
        # Set target for second innings
        session['target'] = session['total_runs'] + 1
        
        # Switch teams for second innings
        session['batting_team'], session['bowling_team'] = session['bowling_team'], session['batting_team']
        
        # Reset score variables for second innings
        session['innings'] = 2
        session['current_over'] = 0
        session['current_ball'] = 0
        session['total_runs'] = 0
        session['wickets'] = 0
        session['score'] = []
        session['batsmen'] = []
        session['striker_index'] = 0
        session['non_striker_index'] = 1
        session['bowlers'] = []
        session['current_bowler'] = None
        session['current_bowler_index'] = -1
        session['previous_bowler'] = None
        session['free_hit'] = False
        session['last_ball_wicket'] = False
        
        return redirect(url_for('select_batsmen'))
    else:
        # Second innings is complete, show match result
        session['second_innings_total'] = session['total_runs']
        session['second_innings_wickets'] = session['wickets']
        session['second_innings_overs'] = f"{session['current_over']}.{session['current_ball']}"
        session['second_innings_batsmen'] = session['batsmen'].copy()
        session['second_innings_bowlers'] = session['bowlers'].copy()
        
        # Determine winner
        if session['first_innings_total'] > session['second_innings_total']:
            session['winner'] = session['team1_name'] if session['team1_name'] == session['bowling_team'] else session['team2_name']
            session['win_margin'] = f"{session['first_innings_total'] - session['second_innings_total']} runs"
            session['win_type'] = "runs"
        elif session['second_innings_total'] > session['first_innings_total']:
            session['winner'] = session['batting_team']
            wickets_left = (len(session['team1']) if session['batting_team'] == session['team1_name'] else len(session['team2'])) - session['wickets']
            session['win_margin'] = f"{wickets_left} wickets"
            session['win_type'] = "wickets"
        else:
            session['winner'] = "Match Tied"
            session['win_margin'] = ""
            session['win_type'] = "tie"
        
        # Calculate Player of the Match
        match_data = {
            'team1_name': session['team1_name'],
            'team2_name': session['team2_name'],
            'team1': session['team1'],
            'team2': session['team2'],
            'first_innings_batsmen': session['first_innings_batsmen'],
            'first_innings_bowlers': session['first_innings_bowlers'],
            'second_innings_batsmen': session['second_innings_batsmen'],
            'second_innings_bowlers': session['second_innings_bowlers'],
            'score': session['score'],
            'winner': session['winner']
        }
        
        potm_engine = PlayerOfTheMatchEngine(match_data)
        session['player_of_match'] = potm_engine.get_player_of_the_match()
        session['top_performers'] = potm_engine.get_top_performers(3)
        
        return render_template('main.html', 
                              page="match_result", 
                              first_innings_total=session['first_innings_total'],
                              first_innings_wickets=session['first_innings_wickets'],
                              first_innings_overs=session['first_innings_overs'],
                              first_innings_batsmen=session['first_innings_batsmen'],
                              first_innings_bowlers=session['first_innings_bowlers'],
                              second_innings_total=session['second_innings_total'],
                              second_innings_wickets=session['second_innings_wickets'],
                              second_innings_overs=session['second_innings_overs'],
                              second_innings_batsmen=session['second_innings_batsmen'],
                              second_innings_bowlers=session['second_innings_bowlers'],
                              winner=session['winner'],
                              win_margin=session['win_margin'],
                              win_type=session['win_type'],
                              team1_name=session['team1_name'],
                              team2_name=session['team2_name'],
                              player_of_match=session['player_of_match'],
                              top_performers=session['top_performers'])
    
@app.route('/switch_strike', methods=['POST'])
def switch_strike():
    # Simply swap the striker and non-striker
    if 'non_striker_index' in session and session['non_striker_index'] != -1:
        session['striker_index'], session['non_striker_index'] = session['non_striker_index'], session['striker_index']
        session.modified = True
    
    return redirect(url_for('score'))

@app.route('/download_summary')
def download_summary():
    # Create a text file in memory
    output = io.StringIO()
    
    # Write match header
    output.write(f"Match Summary: {session['team1_name']} vs {session['team2_name']}\n")
    output.write("=" * 60 + "\n\n")
    
    # Write toss information
    output.write("TOSS INFORMATION\n")
    output.write("-" * 20 + "\n")
    output.write(f"Toss Winner: {session['toss_winner']}\n")
    output.write(f"Batting First: {session['batting_team'] if session['innings'] == 1 else session['bowling_team']}\n\n")
    
    # Write Player of the Match information
    if 'player_of_match' in session and session['player_of_match']:
        output.write("PLAYER OF THE MATCH\n")
        output.write("-" * 20 + "\n")
        output.write(f"{session['player_of_match']['player']} ({session['player_of_match']['team']})\n")
        output.write(f"Performance: {session['player_of_match']['performance']}\n")
        output.write(f"Impact Score: {session['player_of_match']['impact_score']}\n\n")
    
    # Write first innings summary
    output.write("FIRST INNINGS\n")
    output.write("-" * 15 + "\n")
    batting_first_team = session['team1_name'] if session['innings'] == 1 else session['team2_name']
    output.write(f"{batting_first_team}: {session['first_innings_total']}/{session['first_innings_wickets']} in {session['first_innings_overs']} overs\n\n")
    
    output.write("BATTING PERFORMANCE\n")
    output.write("-" * 20 + "\n")
    output.write(f"{'Batsman':<20} {'Runs':<6} {'Balls':<6} {'4s':<4} {'6s':<4} {'SR':<8} {'Status':<15}\n")
    for batsman in session['first_innings_batsmen']:
        strikerate = round(batsman['runs'] / batsman['balls'] * 100, 2) if batsman['balls'] > 0 else 0
        status = f"OUT ({batsman['wicket_type']})" if batsman['out'] else "not out"
        output.write(f"{batsman['name']:<20} {batsman['runs']:<6} {batsman['balls']:<6} {batsman['fours']:<4} {batsman['sixes']:<4} {strikerate:<8.2f} {status:<15}\n")
    output.write("\n")
    
    output.write("BOWLING PERFORMANCE\n")
    output.write("-" * 20 + "\n")
    output.write(f"{'Bowler':<20} {'Overs':<6} {'Maidens':<8} {'Runs':<6} {'Wickets':<8} {'Economy':<8}\n")
    for bowler in session['first_innings_bowlers']:
        overs = f"{bowler['overs']}.{bowler['balls']}"
        economy = bowler.get('economy', 0)
        output.write(f"{bowler['name']:<20} {overs:<6} {bowler['maidens']:<8} {bowler['runs']:<6} {bowler['wickets']:<8} {economy:<8.2f}\n")
    output.write("\n")
    
    # Write second innings summary
    output.write("SECOND INNINGS\n")
    output.write("-" * 15 + "\n")
    batting_second_team = session['team2_name'] if session['innings'] == 1 else session['team1_name']
    output.write(f"{batting_second_team}: {session['second_innings_total']}/{session['second_innings_wickets']} in {session['second_innings_overs']} overs\n\n")
    
    output.write("BATTING PERFORMANCE\n")
    output.write("-" * 20 + "\n")
    output.write(f"{'Batsman':<20} {'Runs':<6} {'Balls':<6} {'4s':<4} {'6s':<4} {'SR':<8} {'Status':<15}\n")
    for batsman in session['second_innings_batsmen']:
        strikerate = round(batsman['runs'] / batsman['balls'] * 100, 2) if batsman['balls'] > 0 else 0
        status = f"OUT ({batsman['wicket_type']})" if batsman['out'] else "not out"
        output.write(f"{batsman['name']:<20} {batsman['runs']:<6} {batsman['balls']:<6} {batsman['fours']:<4} {batsman['sixes']:<4} {strikerate:<8.2f} {status:<15}\n")
    output.write("\n")
    
    output.write("BOWLING PERFORMANCE\n")
    output.write("-" * 20 + "\n")
    output.write(f"{'Bowler':<20} {'Overs':<6} {'Maidens':<8} {'Runs':<6} {'Wickets':<8} {'Economy':<8}\n")
    for bowler in session['second_innings_bowlers']:
        overs = f"{bowler['overs']}.{bowler['balls']}"
        economy = bowler.get('economy', 0)
        output.write(f"{bowler['name']:<20} {overs:<6} {bowler['maidens']:<8} {bowler['runs']:<6} {bowler['wickets']:<8} {economy:<8.2f}\n")
    output.write("\n")
    
    # Write match result
    output.write("MATCH RESULT\n")
    output.write("-" * 12 + "\n")
    if session['win_type'] == "tie":
        output.write("Match Tied\n")
    else:
        output.write(f"{session['winner']} won by {session['win_margin']}\n")
    
    # Write Top Performers section
    if 'top_performers' in session and session['top_performers']:
        output.write("\nTOP PERFORMERS\n")
        output.write("-" * 15 + "\n")
        for i, player in enumerate(session['top_performers'], 1):
            performance_parts = []
            if player.get('runs', 0) > 0:
                performance_parts.append(f"{player['runs']} runs")
            if player.get('wickets', 0) > 0:
                performance_parts.append(f"{player['wickets']} wickets")
                
            performance_str = ", ".join(performance_parts)
            output.write(f"{i}. {player['name']} ({player['team']}): {performance_str} - Impact: {player.get('impact_score', 0):.2f}\n")
    
    # Write match details footer
    output.write("\n" + "=" * 60 + "\n")
    output.write(f"Match recorded on: {datetime.now().strftime('%d-%m-%Y at %H:%M:%S')}\n")
    output.write("Copyright © 2025 Abhinav Panwar. All Rights Reserved.\n")
    
    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime("ON %d-%m-%Y AT %H-%M-%S")
    filename = f"CRICKET MATCH {timestamp}.txt"
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=filename
    )

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
