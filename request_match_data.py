import requests

# Riot API 키 입력
API_KEY = "YOUR_API_KEY"


def get_summoner_puuid(summoner_name):
    """소환사명을 통해 PUUID를 가져오는 함수"""
    url = f"https://kr.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data["puuid"]
    else:
        raise Exception(f"Error: {response.status_code}, {response.json()}")


def get_recent_matches(puuid, count=5):
    """PUUID를 사용해 최근 매치 ID 리스트를 가져오는 함수"""
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&api_key={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error: {response.status_code}, {response.json()}")


def main():
    summoner_name = input("소환사명을 입력하세요: ")
    try:
        # PUUID 가져오기
        puuid = get_summoner_puuid(summoner_name)
        print(f"{summoner_name}의 PUUID: {puuid}")

        # 최근 5개 매치 가져오기
        recent_matches = get_recent_matches(puuid)
        print(f"최근 5개 매치 ID: {recent_matches}")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
