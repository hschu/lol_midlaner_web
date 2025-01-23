## Legue of Legend Midlaner Performance

이 저장소는 리그 오브 레전드 미드라이너의 실력을 측정하는 파이썬 프로그램과 시각화를 위한 웹페이지를 담고 있습니다. 웹페이지는 테스트 목적으로 Render를 활용하여 구현했습니다.

[리그 오브 레전드 미드라이너 실력 지표 웹페이지](https://lol-middle-laner-performance-metric.onrender.com/)

최초 웹페이지 접속시 1분 내외의 대기시간이 발생할 수 있습니다.

로컬에서 실행할 시에는 requirements.txt에 담겨있는 패키지를 설치하시고 아래와 같이 python 코드를 실행하면 됩니다.

```
> python request_match_data.py
```

최초 접속 페이지에서 요구하는 Riot API Key는 직접 Riot Developer에서 발급받으시면 됩니다.
