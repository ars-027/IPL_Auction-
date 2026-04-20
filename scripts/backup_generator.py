import os
import json
import pandas as pd
import pulp

# Same realistic points to match our Ideal Team engine
REALISTIC_POINTS = {
    'Virat Kohli': 98, 'Rohit Sharma': 95, 'MS Dhoni': 95, 'Hardik Pandya': 95,
    'Jasprit Bumrah': 99, 'Rashid Khan': 97, 'Sunil Narine': 96, 'Travis Head': 94,
    'Suryakumar Yadav': 95, 'Shubman Gill': 92, 'Heinrich Klaasen': 94, 'Trent Boult': 92
}

def generate_backups():
    print("\n" + "="*50)
    print("🛡️ BIDBLAZE CORE: BACKUP MATRIX GENERATOR")
    print("="*50)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    
    # 1. Load Data just like before
    all_files = os.listdir(data_dir)
    dfs = []
    for role in ['BAT', 'BOWL', 'AR', 'WK']:
        matched_file = next((f for f in all_files if role in f and f.endswith('.csv') and 'RTM' not in f), None)
        if matched_file:
            df = pd.read_csv(os.path.join(data_dir, matched_file), skiprows=1)
            df.columns = df.columns.str.strip()
            dfs.append(df)

    master_df = pd.concat(dfs, ignore_index=True)
    
    # 2. Clean columns
    player_col = next(c for c in master_df.columns if 'Player' in c)
    role_col = next(c for c in master_df.columns if 'Role' in c)
    price_col = next(c for c in master_df.columns if 'Price' in c)
    points_col = next(c for c in master_df.columns if 'Points' in c)
    origin_col = next(c for c in master_df.columns if 'Origin' in c)

    master_df = master_df.dropna(subset=[player_col, role_col, price_col])

    def clean_price(x):
        try: return float(str(x).replace('₹', '').replace(' Cr', '').strip())
        except: return 0.0

    def assign_points(row):
        player_name = str(row[player_col]).strip()
        pts = str(row[points_col]).upper()
        if 'TB' in pts or 'REVEALED' in pts: return REALISTIC_POINTS.get(player_name, 75.0)
        try: return float(pts)
        except: return 75.0

    master_df['Base Price (Cr)'] = master_df[price_col].apply(clean_price)
    master_df['Final Points'] = master_df.apply(assign_points, axis=1)
    
    # For this test, we will hardcode the ideal team you just generated so we can find backups for them!
    ideal_team_names = [
        "Virat Kohli", "Rohit Sharma", "Suryakumar Yadav", "Travis Head", "Shubman Gill",
        "Rashid Khan", "Jasprit Bumrah", "Mohammed Siraj", "Hardik Pandya", "Sunil Narine",
        "Washington Sundar", "Shivam Dube", "MS Dhoni", "Heinrich Klaasen"
    ]

    ideal_df = master_df[master_df[player_col].isin(ideal_team_names)]
    pool_df = master_df[~master_df[player_col].isin(ideal_team_names)] # Everyone else

    print("Generating 3-Deep Backup Matrix for your Ideal Squad...\n")

    backup_plan = {}

    # 3. Find 3 Backups for every player based on their exact Role and Origin
    for index, ideal_player in ideal_df.iterrows():
        name = str(ideal_player[player_col]).strip()
        role = str(ideal_player[role_col]).strip()
        origin = str(ideal_player[origin_col]).strip()

        # Filter the remaining player pool for matching Role and Origin
        matching_backups = pool_df[(pool_df[role_col].str.strip() == role) & 
                                   (pool_df[origin_col].str.strip() == origin)]
        
        # Sort them by Points (Highest to lowest) and take the top 3
        top_3 = matching_backups.sort_values(by='Final Points', ascending=False).head(3)

        backup_plan[name] = []
        for _, backup in top_3.iterrows():
            backup_plan[name].append({
                "Backup_Name": str(backup[player_col]).strip(),
                "Points": backup['Final Points'],
                "Price": backup['Base Price (Cr)']
            })

    # 4. Print the Output Beautifully
    for player, backups in backup_plan.items():
        role = str(ideal_df[ideal_df[player_col] == player][role_col].values[0]).strip()
        origin = "✈️ OS" if "Overseas" in str(ideal_df[ideal_df[player_col] == player][origin_col].values[0]) else "🇮🇳 IND"
        
        print(f"🎯 TARGET: {player} ({role} | {origin})")
        
        if len(backups) == 0:
            print("   ⚠️ No direct backups available in the database for this specific role/origin!")
        else:
            for i, b in enumerate(backups, 1):
                print(f"   ↳ Plan {i}: {b['Backup_Name']} (Base: ₹{b['Price']} Cr)")
        print("-" * 50)

    # 5. Save it so the UI can use it later
    with open(os.path.join(data_dir, 'strategy_backups.json'), 'w') as f:
        json.dump(backup_plan, f, indent=4)
        
    print("\n✅ SUCCESS: Backup Matrix Generated and Saved to 'strategy_backups.json'!")

if __name__ == "__main__":
    generate_backups()
