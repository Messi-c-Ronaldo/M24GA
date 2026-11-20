"""FM24 Dynamic PA v0.9.5의 포텐 평가 모델 (GPL-3.0-or-later).

원본: FM24_Dynamic_PA_v0.9.5/app 의 model.py, rules.py, model_v07.py, league_strength.py,
scouting_metrics.py, development_balance.py, transfer_evaluation.py.
바꾼 것: 모듈끼리의 import를 패키지 상대 경로로 바꿈. 그 밖의 계산은 원본과 같아요.
모델 입력(선수·시즌 기록)을 만드는 부분은 ../potential.py (M24GA 쪽 새 코드)예요.
"""
