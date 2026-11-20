# 출처: FM24 Dynamic PA v0.9.5 app/fm24_profile.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""FM-specific layout; named to avoid Python's standard-library profile module.

Published FM24 24.4.2+2081827 layout leads, NOT locally live-verified.

Only scalar layout facts are transcribed; implementation is original.
References and limitations are in SOURCES.txt.
Steam/Epic are attempted using the same build layout, never installation paths.
An incompatible or ambiguous build fails closed.
"""
PROFILE_ID='fm24-2442-2081827-research-v1'
LAYOUT={
 'players_start':0x642EDD0,'players_end':0x642EDD8,'player_vtable':0x5A4E958,
 'date':0x631D5BC,'save_root':0x63659C0,'save_id':0x90,'nonce':0xA0,
 'size':0x3E8,'uid':0x284,'dob':0x2BC,'ca':0x200,'pa':0x202,
 'first_name':0x2D0,'last_name':0x2D8,'direct_name':0x2C0,
 'team':0x130,'team_club':0x30,'team_comp':0x50,'comp_uid':0xC,
 'professionalism':0x2F4,'ambition':0x2F1,'determination':0x24A,'work_rate':0x234,'flair':0x231,
 'positions':0x208,'season_stats':0x108,'all_stats':0x48,
}
# The 0x48 selector is a published candidate for the aggregate season block.
# A mandatory user comparison against all-competition stats is required before arming.
POSITIONS=('GK','CB','FB','CB','FB','DM','W','CM','W','W','AM','W','ST','FB','FB')
ADVANCED={'key_passes':0x36,'tackles':0x0E,'interceptions':0x3C,'headers':0x12}
DATE_PATTERN='83 F2 01 8B 05 ?? ?? ?? ?? 66 09'
