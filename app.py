from flask import Flask, jsonify, request, Response
import pandas as pd
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
from utils import convert_int_to_score, convert_score_to_int

app = Flask(__name__)


def get_div_text(lst, to=None, field=None):
    new_list = []
    if field:
        for i in range(len(lst)):
            new_list.append(lst[i][field])
    else:
        for i in range(len(lst)):
            if to == 'int':
                if lst[i].text == ' E ':
                    new_list.append(0)
                elif lst[i].text == ' DNF ':
                    new_list.append(999)
                else:
                    new_list.append(int(lst[i].text))
            else:
                new_list.append(lst[i].text)
    return new_list

def get_html_body(url):
    # Set up the Chrome driver options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run the browser in headless mode (without a GUI)
    # service = Service(executable_path=ChromeDriverManager(version='114.0.5735.90').install())
    # Set up the Chrome driver service
    # Start the Chrome driver
    # driver = webdriver.Chrome(service=service, options=chrome_options)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager(driver_version="116.0.5845.96").install()), options=chrome_options)
    # Load the URL in the browser
    driver.get(url)
    # Wait for the page to fully load (by waiting for the body element to be present)
    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'table-row')))
    # Retrieve the HTML content
    html_content = driver.page_source
    # Clean up
    driver.quit()
    # Use BeautifulSoup to parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    # Return the HTML body element
    return soup

def get_scoreboard(eventID, division, round):
    # TODO: In rounds that are not the first there is a Total column as well as a Round column

    # Retrieve the main body object that we will use for all subsequent queries
    scores_contents = get_html_body('https://www.pdga.com/apps/tournament/live/event?eventId={}&division={}&view=Scores&round={}'.format(eventID, division, str(round)))
    stats_contents = get_html_body('https://www.pdga.com/apps/tournament/live/event?eventId={}&division={}&view=Stats&round={}'.format(eventID, division, str(round)))
    # Total - Round + each hole up until hole selected
    # Get the number of players and the number of holes
    total_players = len(scores_contents.find_all("div", {"class": "table-row"}))
    holes_played = len(stats_contents.find_all("div", {"class": "table-row"}))
    # Get the everything into a DataFrame somehow
    all_holes_scores = scores_contents.find_all('div', class_="hole-cell")
    overall_scores = []
    for player in range(total_players):
        # Goes in order of 1st to last player in sets of n holes
        player_scores = []
        for hole in range(holes_played):
            # Deal with DNFs
            if all_holes_scores[(player * holes_played) + hole].text == ' · ':
                # Player DNFd
                player_scores.append(0)
            else:
                player_scores.append(int(all_holes_scores[(player * holes_played) + hole].text))
        overall_scores.append(player_scores)
    # Get the names player-first-name player-last-name
    first_names = get_div_text(scores_contents.find_all("span", {"class": "player-first-name"}))
    last_names = get_div_text(scores_contents.find_all("span", {"class": "player-last-name"}))
    full_names = []
    for name in range(len(first_names)):
        full_names.append(first_names[name][1:-1] + last_names[name][:-1])
    # Get the hole pars
    hole_pars = get_div_text(scores_contents.find_all("div", {"class": "hole-par"}))
    # Total
    course_par = hole_pars[-1]
    # Retrieve the total score for each player
    # For rounds not equal to 1
    if round != 1:
        total_score = get_div_text(scores_contents.find_all("div", {"style": 'flex-basis: 45px; flex-grow: 1; min-width: 45px;'}), 'int')
    else:
        total_score = [""] * total_players
    # Create a DataFrame out of this information
    columns = ['Position', 'Name', 'Total Score', 'Round Score'] + hole_pars[:-1]
    leaderboard = pd.DataFrame(columns=columns)
    # Add everything we've collected to the DataFrame object
    for row in range(total_players):
        # Create a row object
        new_row = ['', full_names[row], '', ''] + overall_scores[row]
        leaderboard.loc[row] = new_row
    # Calculate each rows score to par
    # Calculate the score for each player for the round in raw strokes
    leaderboard['Total'] = leaderboard.sum(axis=1, numeric_only=True)
    # Convert relative to par
    leaderboard['Round Score'] = leaderboard['Total'] - int(course_par)
    # If the round is round one the round score is the total score
    if round == 1:
        leaderboard['Total Score'] = leaderboard['Round Score']
    else:
        leaderboard['Total Score'] = total_score
    # If there is a row with a total score of 999, remove the row
    leaderboard = leaderboard[leaderboard['Total Score'] != 999]
    leaderboard = leaderboard[leaderboard['Total'] != 0]
    # Now calculate the positions based on total score
    leaderboard['Position'] = leaderboard['Total Score'].rank(method='min').astype(int)
    # Order the leaderboard by Position
    leaderboard = leaderboard.sort_values(by=['Position'])
    return leaderboard

def get_hole_details(event_id, division, round):
    stats_contents = get_html_body('https://www.pdga.com/apps/tournament/live/event?eventId={}&division={}&view=Stats&round={}'.format(event_id, division, str(round)))
    holes_played = len(stats_contents.find_all("div", {"class": "table-row"}))
    hole_details = stats_contents.find_all('div', class_="cell-wrapper")
    holes = []
    for i in range(holes_played):
        hole_name = hole_details[6*i].text
        hole_distance = int(hole_details[6*i + 1].text)
        hole_par = int(hole_details[6*i + 2].text)
        holes.append({'name': hole_name, 'par': hole_par, 'distance': hole_distance})
    return holes

def get_partial_scoreboard(full_round_scoreboard, hole):
    # Taking a full round scoreboard and a hole recalculate the scoreboard up until that hole
    # Firstly, calculate each players score at the start of the round
    starting_scores = full_round_scoreboard[['Name', 'Total Score', 'Round Score']]
    starting_scores['Starting Score'] = starting_scores['Total Score'] - starting_scores['Round Score']
    starting_scores['Partial Score'] = 0
    # For every hole up until hole given as input alter the partial scores
    cols = full_round_scoreboard.columns
    #
    hole_score_df = pd.DataFrame()
    for i in range(hole):
        # Get the par for the hole
        par = int(cols[4 + i])
        hole_scores = pd.DataFrame(full_round_scoreboard.iloc[:, 4 + i])
        scores_to_par = hole_scores - par
        starting_scores['Partial Score'] = starting_scores['Partial Score'] + scores_to_par.iloc[:,0]
        # Create a new DF for the scores_to_par
        hole_score_df['Hole' + str(i + 1)] = scores_to_par
    # Create a new column with the starting score and partial score
    starting_scores['Current Score'] = starting_scores['Starting Score'] + starting_scores['Partial Score']
    # Add the hole scores list for the holes selected (for now front 0 or back nine)
    if hole == 9:
        starting_scores['Hole Scores'] = hole_score_df[:].values.tolist()
        starting_scores = starting_scores[['Name', 'Current Score', 'Partial Score', 'Hole Scores']]
    elif hole == 18:
        starting_scores['Hole Scores'] = hole_score_df[:].values.tolist()
        starting_scores = starting_scores[['Name', 'Current Score', 'Partial Score', 'Hole Scores']]
    # Take the subset of the leaderboard that is relevant
    else:
        starting_scores = starting_scores[['Name', 'Current Score', 'Partial Score']]
    starting_scores['Position'] = starting_scores['Current Score'].rank(method='min').astype(int)
    starting_scores = starting_scores.sort_values(by=['Position'])
    # Prepend a T for any ties
    starting_scores['Position'] = starting_scores['Position'].apply(lambda x: x if len(starting_scores[starting_scores['Position'] == x]) == 1 else 'T' + str(x))
    return starting_scores

def score_progression(players, scoreboard):
    print(players, scoreboard)
    # Take a list of players as input and a whole scoreboard and calculate for each hole the player's hole score, new total score and new leaderboard position and return this in a list of len(number of holes in round)
    # Work out how many holes there are
    holes = len(scoreboard.columns) - 5
    # Result list
    results = []
    for i in range(holes + 1):
        players_hole = []
        for player in players:
            # Get the partial scoreboard
            partial_scoreboard = get_partial_scoreboard(scoreboard, i)
            # Get the relevant row for the player in question
            player_row = partial_scoreboard[partial_scoreboard['Name'] == player]
            player_score = player_row['Current Score'].values[0]
            if player_score > 0:
                player_score = '+' + str(player_score)
            elif player_score == 0:
                player_score = 'E'
            # Also get the players hole score and add it: Birdie, Par, Bogey etc...
            players_hole.append([player, player_score, player_row['Position'].values[0]])
        results.append(players_hole)
    return results

@app.route('/')
def hello_world():
    return jsonify({"message": "Hello, World!"}), 200


@app.route('/gatekeeper-media')
def gatekeeper_score_file():
    event_id = int(request.args.get('event_id'))
    division = request.args.get('division')
    round_number = int(request.args.get('round_number'))
    players = request.args.get('players') # receives it as a string
    players = players[1:-1] # string without the brackets
    players = players.split(',') # split into multiple players
    players = [e[1:-1] for e in players] # remove the added quotations
    
    # Template Columns
    template_columns = ['Position', 'Total Score', 'Round Score', 'Hole', 'Par', 'Distance FT', 'Distance M', 'Player Stroke Count', 'Driving - Fairway Hits', 'Greens In Reg - Cir 1', 'Greens In Reg - Cir 2', 'Scramble', 'O.B. Rate', 'Parked', 'Putting - Cir 1x', 'Putting - Cir 2', 'Player Starting Position', ' Player Starting Score', 'Player Name']
    # Get all of the details we need from PDGA Live
    scores = get_scoreboard(event_id, division, round_number)
    holes = get_hole_details(event_id, division, round_number)
    # Determine if this is using feet or metres. Take the Max distance if > 400 then feet else metres
    distances = list(map(lambda x: x['distance'], holes))
    if max(distances) > 400:
        is_feet = True
    else:
        is_feet = False
    # This will give us all of the details we need
    prog = score_progression(players, scores)
    # Firstly, create templates for all players
    player_templates = []
    for player in players:
        player_template = pd.DataFrame(columns=template_columns)
        player_templates.append(player_template)
    player_round_scores = [0, 0, 0, 0]
    # Given our scoring object is centred around the number of holes, iterate through all the holes
    for i in range(len(holes)):
        # For each hole, we need to get the hole distance in F/M, the Par and the Hole Number
        hole_number = holes[i]['name']
        hole_par = holes[i]['par']
        if is_feet:
            hole_distance_feet = holes[i]['distance']
            hole_distance_metres = int(hole_distance_feet // 3.281)
        if not is_feet: 
            hole_distance_metres = holes[i]['distance']
            hole_distance_feet = int(hole_distance_metres * 3.281)
        # Then for each Player
        for j in range(len(players)):
            # We want to get the players details (after the hole): Position, Total Score, Round Score, Strokes Taken
            player_position = prog[i + 1][j][2]
            player_score = prog[i + 1][j][1]
            current_score = convert_score_to_int(player_score)
            prior_score = convert_score_to_int(prog[i][j][1])
            # Modify the round score for the player
            player_round_scores[j] += (current_score - prior_score)
            player_round_score = convert_int_to_score(player_round_scores[j])
            # this can be either +#, E or -#, we want to convert these to operable integers
            player_hole_score = hole_par + (current_score - prior_score)
            # If it is Hole 1: also store the Player's Name, Starting Score and Starting Position
            if i == 0:
                player_name = players[j]
                # To get the starting position, get the first entry in the prog object. And then get the array associated with the player (same order as given to function)
                player_starting_position = prog[0][j][2]
                player_starting_score = prog[0][j][1]
                # Add row to the player file
                row_to_append = pd.DataFrame([{'Position': player_position, 'Total Score': player_score, 'Round Score': player_round_score, 'Hole': hole_number, 'Par': hole_par, 'Distance FT': hole_distance_feet, 'Distance M': hole_distance_metres, 'Player Stroke Count': player_hole_score, 'Player Starting Position': player_starting_position, ' Player Starting Score': player_starting_score, 'Player Name': player_name}], columns=template_columns)
                player_templates[j] = pd.concat([player_templates[j], row_to_append])
            else:
                row_to_append = pd.DataFrame([{'Position': player_position, 'Total Score': player_score, 'Round Score': player_round_score, 'Hole': hole_number, 'Par': hole_par, 'Distance FT': hole_distance_feet, 'Distance M': hole_distance_metres, 'Player Stroke Count': player_hole_score}], columns=template_columns)
                player_templates[j] = pd.concat([player_templates[j], row_to_append])
    # Now export all templates to file (Tab Separated Table into a .txt file)
    file_data = {}
    for k in range(len(players)):
        player_frame = player_templates[k]
        file_data[f'{players[k]} Round {1}.txt'] = player_frame.to_csv(sep="\t", index=False)
        # player_frame.to_csv(f'{players[k]} Round {1}.txt', sep="\t", index=False)

    # Create a multipart HTTP response to send multiple files
    multipart_data = ""

    for filename, content in file_data.items():
        multipart_data += f'--fileboundary\r\nContent-Disposition: attachment; filename="{filename}"\r\n\r\n{content}\r\n'

    multipart_data += "--fileboundary--"

    response = Response(
        multipart_data,
        content_type="multipart/form-data; boundary=fileboundary",
        status=200
    )

    # Set headers to specify the response as an attachment and provide a default file name
    response.headers["Content-Disposition"] = 'attachment; filename="gatekeeper_player_scores.txt"'

    return response

if __name__ == '__main__':
    app.run()