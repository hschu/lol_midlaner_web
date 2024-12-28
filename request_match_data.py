import requests
import pandas as pd
# Riot API 키 입력
API_KEY = "RGAPI-6091d029-ca97-4de9-abbe-240f68c392f9"

# Riot API 헤더
HEADERS = {"X-Riot-Token": API_KEY}


def get_puuid_by_riot_id(game_name, tag_line):
    """Riot ID를 사용해 PUUID를 가져옴"""
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()["puuid"]
    else:
        raise Exception(f"Error: {response.status_code}, {response.json()}")


def get_recent_matches(puuid, count=5):
    """PUUID를 사용해 최근 매치 ID 리스트를 가져옴"""
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": count}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error: {response.status_code}, {response.json()}")

def match_timeline_info(matchId):
    url_match =f"https://asia.api.riotgames.com/lol/match/v5/matches/{matchId}"
    response_match = requests.get(url_match, headers=HEADERS)
    raw_match = response_match.json()

    url_timeline = f"https://asia.api.riotgames.com/lol/match/v5/matches/{matchId}/timeline"
    response_timeline = requests.get(url_timeline, headers=HEADERS)
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

def main():
    # Riot ID 입력
    # gamer_name = input("Riot ID의 게임 이름 (gameName)을 입력하세요: ")
    # tag_line = input("Riot ID의 태그 (tagLine)를 입력하세요: ")
    gamer_name = "Hide on bush"
    tag_line = "KR1"
    try:
        # Riot ID로 PUUID 가져오기
        puuid = get_puuid_by_riot_id(gamer_name, tag_line)
        print(f"PUUID: {puuid}")

        # PUUID로 최근 매치 ID 가져오기
        recent_matches = get_recent_matches(puuid)
        print(f"최근 5개 매치 ID: {recent_matches}")

        for recent_match in recent_matches:
            match, timeline = match_timeline_info(recent_match)
            isTarget = check_target(match, gamer_name)
            if isTarget['isMid'] and isTarget['isOver20m']:
                # print(f"Gamer: {gamer_name}#{tag_line}, matchId: {recent_match}, isMid: {isTarget['isMid']}, isOver20m: {isTarget['isOver20m']}")
                # print(f"teamid: {isTarget['teamid']}, oteamid: {isTarget['oteamid']}")
                gamer_data = get_gamer_data(match, timeline, isTarget['teamid'])
                opponent_data = get_gamer_data(match, timeline, isTarget['oteamid'])
                print(gamer_data)
                print(opponent_data)

    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()