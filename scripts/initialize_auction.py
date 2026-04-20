import json
import os
import pandas as pd
import re
import sys

# Prevent Windows terminal emoji crashes
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

FRANCHISES = ["MI", "CSK", "RCB", "KKR", "SRH", "DC", "RR", "PBKS", "GT", "LSG", "Deccan", "RPS", "GL"]

def normalize_string(text):
    return re.sub(r'[^a-z0-9]', '', str(text).lower())

def clean_price(x):
    val_str = str(x).upper()
    try:
        num = float(re.sub(r'[^\d.]', '', val_str))
        if 'LAKH' in val_str or 'LACS' in val_str or 'LAC' in val_str: return num / 100.0
        return num
    except: return 0.5

def extract_multiplier(val):
    val_str = str(val).upper()
    if 'NAN' in val_str or 'NONE' in val_str or val_str == '—' or val_str == '-': return 1.05
    try:
        match = re.search(r'([1-9]\.\d+)', val_str)
        if match: return float(match.group(1))
    except: pass
    return 1.05

def setup_auction():
    print("[SYSTEM] Booting Data Engine. Scanning CSVs...")
    script_folder = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(os.path.dirname(script_folder), 'data')
    
    if not os.path.exists(data_folder):
        print("[ERROR] Data folder missing.")
        return

    # Collect RTMs and Data
    team_rtms = {team: [] for team in FRANCHISES}
    all_files = [f for f in os.listdir(data_folder) if f.endswith('.csv')]
    dfs = []

    for file in all_files:
        filepath = os.path.join(data_folder, file)
        try:
            # Smart CSV Loader
            df = pd.read_csv(filepath)
            if any('BIDBLAZE' in str(c).upper() for c in df.columns):
                df = pd.read_csv(filepath, header=1)
            
            # Clean up headers to be perfectly readable
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            # Assign Default Role based on Filename if missing
            file_role = 'BAT'
            if 'BOWL' in file.upper(): file_role = 'BOWL'
            elif 'AR' in file.upper() or 'ALL' in file.upper(): file_role = 'AR'
            elif 'WK' in file.upper() or 'WICKET' in file.upper(): file_role = 'WK'
            df['FILE_ROLE'] = file_role
            
            dfs.append(df)
        except Exception as e:
            print(f"[WARNING] Skipping {file}: {e}")

    if not dfs: return

    master_df = pd.concat(dfs, ignore_index=True)

    # Map the exact columns from your CSVs
    p_col = next((c for c in master_df.columns if 'PLAYER' in c and 'TYPE' not in c), None)
    r_col = next((c for c in master_df.columns if 'ROLE' in c), None)
    o_col = next((c for c in master_df.columns if 'ORIGIN' in c or 'OVERSEAS' in c), None)
    pr_col = next((c for c in master_df.columns if 'PRICE' in c or 'BASE' in c), None)
    pt_col = next((c for c in master_df.columns if 'POINT' in c or 'SCORE' in c), None)
    f_col = next((c for c in master_df.columns if 'FRANCHISE' in c or 'RTM' in c), None)
    s_col = next((c for c in master_df.columns if 'STATUS' in c or 'LEGACY' in c), None)
    t_col = next((c for c in master_df.columns if 'TIER' in c or 'PM' in c), None)

    if not p_col: return
    master_df = master_df.dropna(subset=[p_col])
    
    # Process Exact Data
    master_df['Clean_Price'] = master_df[pr_col].apply(clean_price) if pr_col else 0.5
    master_df['Final_Role'] = master_df[r_col].fillna(master_df['FILE_ROLE']) if r_col else master_df['FILE_ROLE']
    master_df['Tier_Mult'] = master_df[t_col].apply(extract_multiplier) if t_col else 1.05

    def parse_points(val):
        v = str(val).upper()
        if 'TB' in v or 'REVEALED' in v or v == 'NAN' or v == '': return None
        try: return float(re.sub(r'[^\d.]', '', v))
        except: return None

    master_df['Clean_Points'] = master_df[pt_col].apply(parse_points) if pt_col else None

    # Impute TB Revealed Players
    known_df = master_df[master_df['Clean_Points'].notnull()]
    unknown_df = master_df[master_df['Clean_Points'].isnull()]
    
    role_price_means = known_df.groupby(['Final_Role', 'Clean_Price'])['Clean_Points'].mean().to_dict()
    price_means = known_df.groupby('Clean_Price')['Clean_Points'].mean().to_dict()
    max_price = known_df['Clean_Price'].max() if not known_df.empty else 5.0
    max_price_mean = price_means.get(max_price, 85.0)

    def impute_missing(row):
        r, p = row['Final_Role'], row['Clean_Price']
        val = role_price_means.get((r, p), price_means.get(p, max_price_mean + ((p - max_price)*2) if p > max_price else 80.0))
        return min(99.0, round(val * row['Tier_Mult'], 1))

    if not unknown_df.empty:
        master_df.loc[master_df['Clean_Points'].isnull(), 'Clean_Points'] = unknown_df.apply(impute_missing, axis=1)

    # Build Player Database
    player_db = {}
    for _, row in master_df.iterrows():
        name = str(row[p_col]).strip()
        norm_name = normalize_string(name)
        
        is_os = 1 if (o_col and pd.notna(row[o_col]) and 'OVERSEAS' in str(row[o_col]).upper()) else 0
        is_legacy = 1 if (s_col and pd.notna(row[s_col]) and 'LEGACY' in str(row[s_col]).upper()) else 0
        
        # Populate RTM Map
        if f_col and pd.notna(row[f_col]):
            raw_team = str(row[f_col]).upper()
            if raw_team not in ['NAN', 'NONE', '—', '-']:
                for t in FRANCHISES:
                    if t.upper() in raw_team and norm_name not in team_rtms[t]:
                        team_rtms[t].append(norm_name)
        
        r_val = str(row['Final_Role']).upper()
        role_clean = 'BAT'
        if 'BOWL' in r_val: role_clean = 'BOWL'
        elif 'WK' in r_val: role_clean = 'WK'
        elif 'AR' in r_val: role_clean = 'AR'

        player_db[norm_name] = {
            "display_name": name,
            "points": row['Clean_Points'],
            "role": role_clean,
            "is_os": is_os,
            "is_legacy": is_legacy,
            "is_rtm": 0, # Calculated dynamically in UI
            "cost": row['Clean_Price']
        }

    with open(os.path.join(data_folder, 'player_database.json'), 'w', encoding='utf-8') as f:
        json.dump(player_db, f, indent=4)

    # Save State
    state_file = os.path.join(data_folder, 'global_auction_state.json')
    if not os.path.exists(state_file):
        state = {
            "user_settings": { "my_team": "MI", "target_squad_size": 14, "max_overseas": 4, "global_budget": 100.0, "max_rtms": 3 },
            "teams": { t: { "budget_remaining": 100.0, "players_bought": 0, "overseas_bought": 0, "rtms_used": 0, "rtm_cards": team_rtms.get(t, []), "squad": [] } for t in FRANCHISES }
        }
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
    else:
        # Just update RTMs so we don't destroy your live auction state
        with open(state_file, 'r', encoding='utf-8') as f: state = json.load(f)
        for t in FRANCHISES: state['teams'][t]['rtm_cards'] = team_rtms.get(t, [])
        with open(state_file, 'w', encoding='utf-8') as f: json.dump(state, f, indent=4)

    print(f"[SUCCESS] Database Synced! {len(player_db)} Players Extracted.")

if __name__ == "__main__": setup_auction()