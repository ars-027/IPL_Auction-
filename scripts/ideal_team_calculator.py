import os
import json
import pandas as pd
import pulp
import re
import warnings

# Suppress pandas warnings for clean terminal output
warnings.filterwarnings('ignore')

def normalize_string(text):
    """Sanitizes text for perfect 1-to-1 matching across datasets."""
    return re.sub(r'[^a-z0-9]', '', str(text).lower())

def clean_price(x):
    """Fixes the Lakh bug: Converts '₹50 Lakh' to 0.5 and '₹5 Cr' to 5.0"""
    val_str = str(x).upper()
    try:
        num = float(re.sub(r'[^\d.]', '', val_str))
        if 'LAKH' in val_str or 'LACS' in val_str or 'LAC' in val_str:
            return num / 100.0  # Converts 50 Lakh to 0.5 Cr
        return num
    except:
        return 0.5

def get_expected_price(points, base_price):
    """Calculates the realistic auction price based on player performance."""
    if points >= 95: exp = 16.0
    elif points >= 90: exp = 10.0
    elif points >= 85: exp = 6.5
    elif points >= 80: exp = 3.5
    elif points >= 75: exp = 1.5
    else: exp = 0.5
    # Ensure the expected price never falls below their actual base price
    return max(base_price, exp)

def get_column(columns, keywords, exclude=None):
    """Smart column detector to bypass messy CSV header formats."""
    for c in columns:
        c_up = str(c).strip().upper()
        if any(k in c_up for k in keywords):
            if exclude and any(e in c_up for e in exclude): continue
            return c
    return None

def calculate_ideal_team():
    print("\n" + "═"*80)
    print("🧠 BIDBLAZE QUANT CORE: REALISTIC SQUAD OPTIMIZATION")
    print("═"*80)

    # 1. State Retrieval
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    state_file = os.path.join(data_dir, 'global_auction_state.json')

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ FATAL ERROR: Cannot read system state. ({e})")
        return

    my_team = state['user_settings'].get('my_team', 'MI')
    team_data = state['teams'].get(my_team, {})
    
    budget = float(team_data.get('budget_remaining', 100.0))
    squad_size = int(state['user_settings'].get('target_squad_size', 14))
    max_os = int(state['user_settings'].get('max_overseas', 4))
    raw_rtms = team_data.get('rtm_cards', [])
    
    normalized_rtms = {normalize_string(rtm): rtm for rtm in raw_rtms}

    print(f"➤ Franchise Entity: {my_team}")
    print(f"➤ Constraints: {squad_size} Roster Slots | Max {max_os} Overseas | Liquidity: ₹{budget:.2f} Cr\n")

    # 2. Data Pipeline Construction
    dfs = []
    for role in ['BAT', 'BOWL', 'AR', 'WK']:
        filepath = os.path.join(data_dir, f'{role}.csv')
        if os.path.exists(filepath):
            try:
                # Bypass the title row and read the headers
                df = pd.read_csv(filepath, header=1)
                df.columns = df.columns.str.strip()
                df['Calculated_Role'] = role 
                dfs.append(df)
            except Exception as e: pass

    if not dfs:
        print("❌ CRITICAL: Market data is empty. Verify CSV files in the data directory.")
        return

    master_df = pd.concat(dfs, ignore_index=True)
    
    # 3. Secure Data Cleansing
    p_col = get_column(master_df.columns, ['PLAYER', 'NAME'], exclude=['NO', 'ID'])
    pr_col = get_column(master_df.columns, ['PRICE', 'BASE'])
    pt_col = get_column(master_df.columns, ['POINTS', 'SCORE'])
    o_col = get_column(master_df.columns, ['ORIGIN', 'OVERSEAS'])

    master_df = master_df.dropna(subset=[p_col, pr_col])
    master_df['Clean_Price'] = master_df[pr_col].apply(clean_price)
    
    def parse_points(val):
        v = str(val).upper()
        if 'TB' in v or 'REVEALED' in v or v == 'NAN' or v == '': return None
        try: return float(v)
        except: return None

    master_df['Clean_Points'] = master_df[pt_col].apply(parse_points) if pt_col else None
    master_df['Is_OS'] = master_df[o_col].apply(lambda x: 1 if pd.notna(x) and 'OVERSEAS' in str(x).upper() else 0) if o_col else 0
    master_df['Norm_Name'] = master_df[p_col].apply(normalize_string)
    master_df['Is_RTM'] = master_df['Norm_Name'].apply(lambda x: 1 if x in normalized_rtms else 0)

    # 4. Statistical Imputation Engine
    known_df = master_df[master_df['Clean_Points'].notnull()]
    unknown_df = master_df[master_df['Clean_Points'].isnull()]
    
    print(f"📊 [DATA PIPELINE] Known Assets: {len(known_df)} | TB Revealed Assets: {len(unknown_df)}")

    role_price_means = known_df.groupby(['Calculated_Role', 'Clean_Price'])['Clean_Points'].mean().to_dict()
    price_means = known_df.groupby('Clean_Price')['Clean_Points'].mean().to_dict()
    max_known_price = known_df['Clean_Price'].max() if not known_df.empty else 5.0
    max_known_price_mean = price_means.get(max_known_price, 85.0)

    def impute_missing_points(row):
        r = row['Calculated_Role']
        p = row['Clean_Price']
        
        if pd.notna(role_price_means.get((r, p))): val = role_price_means[(r, p)]
        elif pd.notna(price_means.get(p)): val = price_means[p]
        elif p > max_known_price: val = max_known_price_mean + ((p - max_known_price) * 2.0)
        else: val = 80.0
            
        return min(99.0, round(val * 1.05, 1)) # Apply 5% Marquee Premium

    if not unknown_df.empty:
        master_df.loc[master_df['Clean_Points'].isnull(), 'Clean_Points'] = unknown_df.apply(impute_missing_points, axis=1)

    # 5. Build Dictionaries & Calculate Expected Costs
    player_dict = {}
    for _, row in master_df.iterrows():
        name = row['Norm_Name']
        if name not in player_dict:
            pts = row['Clean_Points']
            base = row['Clean_Price']
            exp_cost = get_expected_price(pts, base) # THE REALISTIC PRICE ENGINE

            player_dict[name] = {
                'display_name': row[p_col], 'cost': exp_cost, 'base_price': base,
                'points': pts, 'role': row['Calculated_Role'], 'is_os': row['Is_OS'], 'is_rtm': row['Is_RTM']
            }

    players = list(player_dict.keys())

    # 6. Linear Programming Optimization
    prob = pulp.LpProblem("Franchise_Value_Optimization", pulp.LpMaximize)
    player_vars = pulp.LpVariable.dicts("Player", players, cat='Binary')

    # Objective: Maximize Performance
    prob += pulp.lpSum([player_dict[p]['points'] * player_vars[p] for p in players]), "Maximize_Total_Points"

    # Core Constraints (Using EXPECTED cost, not Base Price)
    prob += pulp.lpSum([player_vars[p] for p in players]) == squad_size, "Exact_Roster_Size"
    prob += pulp.lpSum([player_dict[p]['cost'] * player_vars[p] for p in players]) <= budget, "Liquidity_Limit"
    prob += pulp.lpSum([player_dict[p]['is_os'] * player_vars[p] for p in players]) <= max_os, "Overseas_Cap"

    # RTM Locking
    for p in players:
        if player_dict[p]['is_rtm'] == 1:
            prob += player_vars[p] == 1, f"Lock_RTM_{p}"

    # Positional Rulebook Constraints
    prob += pulp.lpSum([player_vars[p] for p in players if player_dict[p]['role'] == 'BAT']) >= max(3, squad_size // 4), "Min_BAT"
    prob += pulp.lpSum([player_vars[p] for p in players if player_dict[p]['role'] == 'BOWL']) >= max(3, squad_size // 4), "Min_BOWL"
    prob += pulp.lpSum([player_vars[p] for p in players if player_dict[p]['role'] == 'AR']) >= max(1, squad_size // 6), "Min_AR"
    prob += pulp.lpSum([player_vars[p] for p in players if player_dict[p]['role'] == 'WK']) >= 1, "Min_WK"

    # Execute Solver
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # 7. Executive Output Generation
    if pulp.LpStatus[prob.status] == 'Optimal':
        print("\n✅ ALGORITHM SUCCESS: Optimal Matrix Discovered\n")
        
        financials = {'BAT': 0.0, 'BOWL': 0.0, 'AR': 0.0, 'WK': 0.0}
        total_points = 0.0
        total_cost = 0.0
        
        print(f"{'PLAYER ASSET':<22} | {'ROLE':<5} | {'ORIGIN':<8} | {'EST COST':<10} | {'STRATEGY'}")
        print("-" * 80)
        
        for p in players:
            if player_vars[p].varValue == 1.0:
                data = player_dict[p]
                financials[data['role']] += data['cost']
                total_cost += data['cost']
                total_points += data['points']
                
                origin_str = "✈️ OS" if data['is_os'] else "DOM"
                marker = "🔄 RE-ACQUIRE (RTM)" if data['is_rtm'] else "🎯 AGGRESSIVE BUY"
                
                print(f"{data['display_name']:<22} | {data['role']:<5} | {origin_str:<8} | ₹{data['cost']:<6.2f} Cr | {marker}")

        print("-" * 80)
        print(f"📊 PERFORMANCE YIELD : ⭐ {total_points:.1f} Total Points")
        print(f"💰 CAPITAL EXPENDED  : ₹{total_cost:.2f} Cr (Expected Auction Price)")
        print(f"🏦 LIQUIDITY SURPLUS : ₹{(budget - total_cost):.2f} Cr\n")
            
    else:
        print("\n❌ ALGORITHM FAILED (INFEASIBLE MATRIX)")
        print("\n[DIAGNOSTIC TRACE]")
        print("The solver could not find a mathematical combination within your ₹100 Cr budget. ")
        print("Cause: Your 'Locked' RTM players trigger bidding wars that are too expensive, leaving you unable to afford the remaining 11 bench players at Base Price (₹0.5 Cr).")

if __name__ == "__main__":
    calculate_ideal_team()