from flask import Flask, request, render_template
import requests
import pandas as pd
import numpy as np

# Flask 앱 생성
app = Flask(__name__)

# Riot API 키 입력
# API_KEY = "RGAPI-386cd3ac-a127-4203-aadc-678f4c384306"

# Riot API 헤더
# HEADERS = {"X-Riot-Token": API_KEY}

parameter = pd.read_json("./parameters.json")

normalize_parameter = {
    "af14combatscore" : [-3.233195355409694, 3.516596413521268],
    "af14managescore" : [-4.542339666904909, 5.624995815720527],
    "af14diffscore" :   [-4.729157179754498, 4.102997024016695],
    "af14totalscore"  : [-3.407761520729901, 3.8728473615099612]
}

total_parameters = {
    "std" :    [1.23078432, 1.27640612, 1.16705394],
    "weight" : [0.44091245, 0.36296359, 0.46178546]
}

average_score = {
    "combat" : 47.90066814048947,
    "manage" : 44.67581181586009,
    "diff"   : 53.54477594758504,
    "total"  : 46.8059962545538
}

def get_puuid_by_riot_id(game_name, tag_line, headers):
    """Riot ID를 사용해 PUUID를 가져옴"""
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["puuid"]
    else:
        raise Exception(f"Error: {response.status_code}, {response.json()}")

def get_recent_matches(puuid, headers, count=5):
    """PUUID를 사용해 최근 매치 ID 리스트를 가져옴"""
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": count}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error: {response.status_code}, {response.json()}")

def match_timeline_info(matchId, headers):
    url_match =f"https://asia.api.riotgames.com/lol/match/v5/matches/{matchId}"
    response_match = requests.get(url_match, headers=headers)
    raw_match = response_match.json()

    url_timeline = f"https://asia.api.riotgames.com/lol/match/v5/matches/{matchId}/timeline"
    response_timeline = requests.get(url_timeline, headers=headers)
    raw_timeline = response_timeline.json()

    if (response_match.status_code == 200) and (response_timeline.status_code == 200):
        return raw_match, raw_timeline
    else:
        raise Exception(f"Error: {response_match.status_code}, {response_timeline.status_code}")

def check_target(match, gamer_name):
    isMid = False
    isOver20m = False
    teamid = -1
    oteamid = -1

    for pid, participant in enumerate(match['info']['participants']):
        if participant['riotIdGameName'] == gamer_name:
            if participant['teamPosition'] == "MIDDLE":
                isMid = True
                teamid = pid
        else:
            if participant['teamPosition'] == "MIDDLE":
                oteamid = pid

    if match['info']['gameDuration'] > 1200:
        isOver20m = True

    isTarget = {
        "isMid": isMid,
        "isOver20m": isOver20m,
        "teamid": teamid,
        "oteamid": oteamid
    }

    return isTarget

def get_gamer_data(match, timeline, pid):
    target_data = {}
    target_data['win']           = match['info']['participants'][pid]['win']
    target_data['gameDuration']  = match['info']['participants'][pid]['challenges']['gameLength']
    target_data['participantId'] = match['info']['participants'][pid]['participantId']

    target_data['kills']   = match['info']['participants'][pid]['kills']
    target_data['deaths']  = match['info']['participants'][pid]['deaths']
    target_data['assists'] = match['info']['participants'][pid]['assists']

    # solo KD 계산 (mid vs mid가 아닌 mid와 1:1 대결에서 승리)
    solo_kill, solo_death = 0, 0
    for frame in timeline['info']['frames']:
        for event in frame['events']:
            if (event['type'] == "CHAMPION_KILL") and ('assistingParticipantIds' not in event):
                if (event['killerId'] == pid + 1):
                    solo_kill += 1
                elif (event['victimId'] == pid + 1):
                    solo_death += 1

    target_data['solokills'] = solo_kill
    target_data['solodeaths'] = solo_death

    target_data['totalDamageDealtToChampions'] = match['info']['participants'][pid]['totalDamageDealtToChampions']
    target_data['totalDamageTaken']            = match['info']['participants'][pid]['totalDamageTaken']
    target_data['totalMinionsKilled']          = match['info']['participants'][pid]['totalMinionsKilled']
    target_data['totalCS'] = target_data['totalMinionsKilled'] + match['info']['participants'][pid]['neutralMinionsKilled']
    target_data['totalXp'] = timeline['info']['frames'][-1]['participantFrames'][str(target_data['participantId'])]['xp']
    target_data['goldEarned'] = match['info']['participants'][pid]['goldEarned']

    # 분당 기준 데이터
    target_data['dpm']  = target_data['totalDamageDealtToChampions'] / (target_data['gameDuration'] / 60)
    target_data['dtpm'] = target_data['totalDamageTaken'] / (target_data['gameDuration'] / 60)
    target_data['dpd']  = target_data['totalDamageDealtToChampions'] / (1 if target_data['deaths'] == 0 else target_data['deaths'])
    target_data['dpg']  = target_data['totalDamageDealtToChampions'] / target_data['goldEarned']
    target_data['gpm']  = target_data['goldEarned'] / (target_data['gameDuration'] / 60)
    target_data['xpm']  = target_data['totalXp'] / (target_data['gameDuration'] / 60)
    target_data['cspm'] = target_data['totalCS'] / (target_data['gameDuration'] / 60)
    target_data['mpm']  = target_data['totalMinionsKilled'] / (target_data['gameDuration'] / 60)

    # 라인전(14분) 까지의 데이터
    at14_target_data = {}
    match_timeline_to14 = timeline['info']['frames'][:15]
    at14_kill, at14_death, at14_assist = 0, 0, 0
    at14_solo_kill, at14_solo_death = 0, 0
    for frame in match_timeline_to14:
        for event in frame['events']:
            if (event['type'] == "CHAMPION_KILL") and ('assistingParticipantIds' not in event):
                if (event['killerId'] == pid + 1):
                    at14_solo_kill += 1
                    at14_kill += 1
                    # break
                elif (event['victimId'] == pid + 1):
                    at14_solo_death += 1
                    at14_death += 1
                    # break
            elif (event['type'] == "CHAMPION_KILL"):
                if (pid + 1) in event['assistingParticipantIds']:
                    at14_assist += 1
                    # break
                elif (event['killerId'] == pid + 1):
                    at14_kill += 1
                    # break
                elif (event['victimId'] == pid + 1):
                    at14_death += 1
                    # break
    at14_target_data['kills'] = at14_kill
    at14_target_data['deaths'] = at14_death
    at14_target_data['assists'] = at14_assist
    at14_target_data['solokills'] = at14_solo_kill
    at14_target_data['solodeaths'] = at14_solo_death

    # 라인전(14분) 시점의 데이터
    match_timeline_at14 = timeline['info']['frames'][14]
    match_timeline_at14_target = match_timeline_at14['participantFrames'][str(target_data['participantId'])]

    # 라인전(14분) 시점의 데미지, 미니언, 경험치, 골드, CS 지표
    jungleMinionsKilled = 0 if 'jungleMinionsKilled' not in match_timeline_at14_target else match_timeline_at14_target['jungleMinionsKilled']
    at14_target_data['gameDuration'] = match_timeline_at14['timestamp'] / 1000
    at14_target_data['totalDamageDealtToChampions'] = match_timeline_at14_target['damageStats']['totalDamageDoneToChampions']
    at14_target_data['totalDamageTaken'] = match_timeline_at14_target['damageStats']['totalDamageTaken']
    at14_target_data['totalMinionsKilled'] = match_timeline_at14_target['minionsKilled']
    at14_target_data['totalCS'] = at14_target_data['totalMinionsKilled'] + jungleMinionsKilled
    at14_target_data['totalXp'] = match_timeline_at14_target['xp']
    at14_target_data['goldEarned'] = match_timeline_at14_target['totalGold']

    # 라인전(14분) 시점의 분당 기준 데이터
    at14_target_data['dpm'] = at14_target_data['totalDamageDealtToChampions'] / (at14_target_data['gameDuration'] / 60)
    at14_target_data['dtpm'] = at14_target_data['totalDamageTaken'] / (at14_target_data['gameDuration'] / 60)
    at14_target_data['dpd'] = at14_target_data['totalDamageDealtToChampions'] / (1 if at14_target_data['deaths'] == 0 else at14_target_data['deaths'])
    at14_target_data['dpg'] = at14_target_data['totalDamageDealtToChampions'] / at14_target_data['goldEarned']
    at14_target_data['gpm'] = at14_target_data['goldEarned'] / (at14_target_data['gameDuration'] / 60)
    at14_target_data['xpm'] = at14_target_data['totalXp'] / (at14_target_data['gameDuration'] / 60)
    at14_target_data['cspm'] = at14_target_data['totalCS'] / (at14_target_data['gameDuration'] / 60)
    at14_target_data['mpm'] = at14_target_data['totalMinionsKilled'] / (at14_target_data['gameDuration'] / 60)
    target_data['at14'] = at14_target_data

    # 라인전(14분) 이후 데이터 - 전체에서 14분까지 데이터를 처리함
    af14_target_data = {}
    af14_target_data['kills'] = target_data['kills'] - at14_target_data['kills']
    af14_target_data['deaths'] = target_data['deaths'] - at14_target_data['deaths']
    af14_target_data['assists'] = target_data['assists'] - at14_target_data['assists']
    af14_target_data['solokills'] = target_data['solokills'] - at14_target_data['solokills']
    af14_target_data['solodeaths'] = target_data['solodeaths'] - at14_target_data['solodeaths']

    # 라인전(14분) 시점의 데미지, 미니언, 경험치, 골드, CS 지표
    af14_target_data['gameDuration'] = target_data['gameDuration'] - at14_target_data['gameDuration']
    af14_target_data['totalDamageDealtToChampions'] = target_data['totalDamageDealtToChampions'] - at14_target_data['totalDamageDealtToChampions']
    af14_target_data['totalDamageTaken'] = target_data['totalDamageTaken'] - at14_target_data['totalDamageTaken']
    af14_target_data['totalMinionsKilled'] = target_data['totalMinionsKilled'] - at14_target_data['totalMinionsKilled']
    af14_target_data['totalCS'] = target_data['totalCS'] - at14_target_data['totalCS']
    af14_target_data['totalXp'] = target_data['totalXp'] - at14_target_data['totalXp']
    af14_target_data['goldEarned'] = target_data['goldEarned'] - at14_target_data['goldEarned']

    # 라인전(14분) 시점의 분당 기준 데이터
    af14_target_data['dpm'] = af14_target_data['totalDamageDealtToChampions'] / (af14_target_data['gameDuration'] / 60)
    af14_target_data['dtpm'] = af14_target_data['totalDamageTaken'] / (af14_target_data['gameDuration'] / 60)
    af14_target_data['dpd'] = af14_target_data['totalDamageDealtToChampions'] / (1 if af14_target_data['deaths'] == 0 else af14_target_data['deaths'])
    af14_target_data['dpg'] = af14_target_data['totalDamageDealtToChampions'] / af14_target_data['goldEarned']
    af14_target_data['gpm'] = af14_target_data['goldEarned'] / (af14_target_data['gameDuration'] / 60)
    af14_target_data['xpm'] = af14_target_data['totalXp'] / (af14_target_data['gameDuration'] / 60)
    af14_target_data['cspm'] = af14_target_data['totalCS'] / (af14_target_data['gameDuration'] / 60)
    af14_target_data['mpm'] = af14_target_data['totalMinionsKilled'] / (af14_target_data['gameDuration'] / 60)
    target_data['af14'] = af14_target_data

    return target_data

def merge_data(target, opponent):
    match_data = {}
    match_data['win'] = target['win']
    at14killsRatio =0
    if not (target['at14']['kills'] == 0 and opponent['at14']['kills'] == 0):
        at14killsRatio = target['at14']['kills'] / (target['at14']['kills'] + opponent['at14']['kills'])

    at14deathsRatio = 0
    if not (target['at14']['deaths'] == 0 and opponent['at14']['deaths'] == 0):
        at14deathsRatio = target['at14']['deaths'] / (target['at14']['deaths'] + opponent['at14']['deaths'])

    at14assistsRatio = 0
    if not (target['at14']['assists'] == 0 and opponent['at14']['assists'] == 0):
        at14assistsRatio = target['at14']['assists'] / (target['at14']['assists'] + opponent['at14']['assists'])

    at14solokillsRatio = 0
    if not (target['at14']['solokills'] == 0 and opponent['at14']['solokills'] == 0):
        at14solokillsRatio = target['at14']['solokills'] / (target['at14']['solokills'] + opponent['at14']['solokills'])

    at14solodeathsRatio = 0
    if not (target['at14']['solodeaths'] == 0 and opponent['at14']['solodeaths'] == 0):
        at14solodeathsRatio = target['at14']['solodeaths'] / (target['at14']['solodeaths'] + opponent['at14']['solodeaths'])

    # at14
    match_data['at14killsRatio']      = at14killsRatio
    match_data['at14deathsRatio']     = at14deathsRatio
    match_data['at14assistsRatio']    = at14assistsRatio
    match_data['at14solokillsRatio']  = at14solokillsRatio
    match_data['at14solodeathsRatio'] = at14solodeathsRatio
    match_data['at14dpm']             = target['at14']['dpm']
    match_data['at14dtpm']            = target['at14']['dtpm']
    match_data['at14cspm']            = target['at14']['cspm']
    match_data['at14gpm']             = target['at14']['gpm']
    match_data['at14xpm']             = target['at14']['xpm']
    match_data['at14dpd']             = target['at14']['dpd']
    match_data['at14dpg']             = target['at14']['dpg']
    match_data['at14dpmdiff']         = target['at14']['dpm'] - opponent['at14']['dpm']
    match_data['at14dtpmdiff']        = target['at14']['dtpm'] - opponent['at14']['dtpm']
    match_data['at14cspmdiff']        = target['at14']['cspm'] - opponent['at14']['cspm']
    match_data['at14gpmdiff']         = target['at14']['gpm'] - opponent['at14']['gpm']
    match_data['at14xpmdiff']         = target['at14']['xpm'] - opponent['at14']['xpm']
    match_data['at14dpddiff']         = target['at14']['dpd'] - opponent['at14']['dpd']
    match_data['at14dpgdiff']         = target['at14']['dpg'] - opponent['at14']['dpg']

    af14killsRatio = 0
    if not (target['af14']['kills'] == 0 and opponent['af14']['kills'] == 0):
        af14killsRatio = target['af14']['kills'] / (target['af14']['kills'] + opponent['af14']['kills'])

    af14deathsRatio = 0
    if not (target['af14']['deaths'] == 0 and opponent['af14']['deaths'] == 0):
        af14deathsRatio = target['af14']['deaths'] / (target['af14']['deaths'] + opponent['af14']['deaths'])

    af14assistsRatio = 0
    if not (target['af14']['assists'] == 0 and opponent['af14']['assists'] == 0):
        af14assistsRatio = target['af14']['assists'] / (target['af14']['assists'] + opponent['af14']['assists'])

    af14solokillsRatio = 0
    if not (target['af14']['solokills'] == 0 and opponent['af14']['solokills'] == 0):
        af14solokillsRatio = target['af14']['solokills'] / (target['af14']['solokills'] + opponent['af14']['solokills'])

    af14solodeathsRatio = 0
    if not (target['af14']['solodeaths'] == 0 and opponent['af14']['solodeaths'] == 0):
        af14solodeathsRatio = target['af14']['solodeaths'] / (target['af14']['solodeaths'] + opponent['af14']['solodeaths'])

    # af14
    match_data['af14killsRatio']      = af14killsRatio
    match_data['af14deathsRatio']     = af14deathsRatio
    match_data['af14assistsRatio']    = af14assistsRatio
    match_data['af14solokillsRatio']  = af14solokillsRatio
    match_data['af14solodeathsRatio'] = af14solodeathsRatio
    match_data['af14dpm']             = target['af14']['dpm']
    match_data['af14dtpm']            = target['af14']['dtpm']
    match_data['af14cspm']            = target['af14']['cspm']
    match_data['af14gpm']             = target['af14']['gpm']
    match_data['af14xpm']             = target['af14']['xpm']
    match_data['af14dpd']             = target['af14']['dpd']
    match_data['af14dpg']             = target['af14']['dpg']
    match_data['af14dpmdiff']         = target['af14']['dpm'] - opponent['af14']['dpm']
    match_data['af14dtpmdiff']        = target['af14']['dtpm'] - opponent['af14']['dtpm']
    match_data['af14cspmdiff']        = target['af14']['cspm'] - opponent['af14']['cspm']
    match_data['af14gpmdiff']         = target['af14']['gpm'] - opponent['af14']['gpm']
    match_data['af14xpmdiff']         = target['af14']['xpm'] - opponent['af14']['xpm']
    match_data['af14dpddiff']         = target['af14']['dpd'] - opponent['af14']['dpd']
    match_data['af14dpgdiff']         = target['af14']['dpg'] - opponent['af14']['dpg']

    return match_data

def compute_score(data):
    # combat
    combat_score = 0
    af14combat = ['af14killsRatio', 'af14deathsRatio', 'af14assistsRatio', 'af14solokillsRatio', 'af14solodeathsRatio', 'af14dpm', 'af14dtpm']
    for c in af14combat:
        combat_score += parameter['weight'][0][c] * (data[c] - parameter['mean'][0][c]) / parameter['std'][0][c]
    norm_combat_score = (combat_score - normalize_parameter['af14combatscore'][0]) / (normalize_parameter['af14combatscore'][1] - normalize_parameter['af14combatscore'][0]) * 100

    # manage
    manage_score = 0
    af14manage = ['af14cspm', 'af14gpm', 'af14xpm', 'af14dpd', 'af14dpg']
    for c in af14manage:
        manage_score += parameter['weight'][0][c] * (data[c] - parameter['mean'][0][c]) / parameter['std'][0][c]
    norm_manage_score = (manage_score - normalize_parameter['af14managescore'][0]) / (normalize_parameter['af14managescore'][1] - normalize_parameter['af14managescore'][0]) * 100

    # diff
    diff_score = 0
    af14diff = ['af14dpmdiff', 'af14dtpmdiff', 'af14cspmdiff', 'af14gpmdiff', 'af14xpmdiff', 'af14dpddiff', 'af14dpgdiff']
    for c in af14diff:
        diff_score += parameter['weight'][0][c] * (data[c] - parameter['mean'][0][c]) / parameter['std'][0][c]
    norm_diff_score = (diff_score - normalize_parameter['af14diffscore'][0]) / (normalize_parameter['af14diffscore'][1] - normalize_parameter['af14diffscore'][0]) * 100

    total_score = total_parameters['weight'][0] / total_parameters['std'][0] * combat_score + \
                  total_parameters['weight'][1] / total_parameters['std'][1] * manage_score + \
                  total_parameters['weight'][2] / total_parameters['std'][2] * diff_score
    norm_total_score = (total_score - normalize_parameter['af14totalscore'][0]) / (normalize_parameter['af14totalscore'][1] - normalize_parameter['af14totalscore'][0]) * 100
    scores = {
        "combat" : norm_combat_score,
        "manage" : norm_manage_score,
        "diff"   : norm_diff_score,
        "total"  : norm_total_score,
        "win" : data['win']
    }
    return scores


# 라우트: 메인 페이지
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            # 입력값 가져오기
            riot_api_key = request.form["riot_api_key"]
            game_name = request.form["game_name"]
            tag_line = request.form["tag_line"]

            headers = {"X-Riot-Token": riot_api_key}

            # Riot ID로 PUUID 가져오기
            puuid = get_puuid_by_riot_id(game_name, tag_line, headers)


            # PUUID로 최근 매치 가져오기
            recent_matches = get_recent_matches(puuid, headers, count=10)
            results = []
            for recent_match in recent_matches:
                match, timeline = match_timeline_info(recent_match, headers)
                isTarget = check_target(match, game_name)
                if isTarget['isMid'] and isTarget['isOver20m']:
                    # print(f"Gamer: {gamer_name}#{tag_line}, matchId: {recent_match}, isMid: {isTarget['isMid']}, isOver20m: {isTarget['isOver20m']}")
                    # print(f"teamid: {isTarget['teamid']}, oteamid: {isTarget['oteamid']}")
                    gamer_data = get_gamer_data(match, timeline, isTarget['teamid'])
                    opponent_data = get_gamer_data(match, timeline, isTarget['oteamid'])
                    merged_data = merge_data(gamer_data, opponent_data)
                    scores = compute_score(merged_data)
                    scores['matchId'] = recent_match
                    results.append(scores)
            return render_template("result.html", game_name=game_name, tag_line=tag_line, results=results, average_score=average_score)
        except Exception as e:
            return render_template("index.html", error=str(e))
    return render_template("index.html")

# Flask 앱 실행
if __name__ == "__main__":
    app.run(debug=True)