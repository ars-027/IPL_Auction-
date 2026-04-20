import json
import os
import time

def get_top7_points(squad):
    """Calculates the true Top 7 points mathematically aligned with Official Rulebook constraints"""
    counts = {'BAT': 0, 'BOWL': 0, 'WK': 0, 'AR': 0}
    os_count = 0
    total_points = 0
    
    # Sort squad by highest points to ensure optimal Top 7 selection
    sorted_squad = sorted(squad, key=lambda x: x.get('points', 0), reverse=True)
    rules = {'BAT': 3, 'BOWL': 2, 'WK': 1, 'AR': 1}
    
    for p in sorted_squad:
        r = str(p.get('role', 'BAT')).upper()
        if 'BAT' in r: r = 'BAT'
        elif 'BOWL' in r: r = 'BOWL'
        elif 'WK' in r: r = 'WK'
        elif 'AR' in r: r = 'AR'
        else: r = 'BAT'
        
        is_os = p.get('is_os', False)
        
        # Enforce strict 3-2-1-1 positional rules and Overseas limits
        if counts[r] < rules[r]:
            if is_os and os_count >= 3:
                continue # Skip player if it breaches the OS limit constraint
            
            counts[r] += 1
            if is_os: 
                os_count += 1
            total_points += p.get('points', 0)
            
    return total_points

def generate_executive_insights():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    state_file = os.path.join(data_dir, 'global_auction_state.json')

    # 1. Thread-Safe Data Ingestion (Bypass Node.js file locks)
    state = None
    for _ in range(10):
        try:
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                break
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.05)
        except Exception:
            time.sleep(0.05)

    if not state or 'teams' not in state:
        return

    # 2. Macro-Economic Market Calculation
    target_size = int(state.get('user_settings', {}).get('target_squad_size', 14))
    global_liquidity = 0.0
    global_demand = 0

    team_metrics = []

    for team, data in state['teams'].items():
        bought = data.get('players_bought', 0)
        slots_left = max(0, target_size - bought)
        purse = data.get('budget_remaining', 0.0)
        
        # Aggregate global economy data
        global_liquidity += purse
        global_demand += slots_left
        
        # Purchasing Power Parity (PPP) - Prevents Division by Zero
        ppp = (purse / slots_left) if slots_left > 0 else 0.0
        
        # Determine actual compliance points
        squad = data.get('squad', [])
        points = get_top7_points(squad)

        team_metrics.append({
            "team": team, 
            "ppp": ppp, 
            "purse": purse, 
            "slots_left": slots_left,
            "points": points
        })

    # Sort franchises strictly by their Purchasing Power Parity (Highest leverage to Lowest)
    team_metrics.sort(key=lambda x: x['ppp'], reverse=True)

    # 3. Executive Market State Analysis
    inflation_index = (global_liquidity / global_demand) if global_demand > 0 else 0.0
    
    market_state = "STABLE"
    advice = "Execute planned bidding strategy. Standard value metrics apply."
    
    if inflation_index > 7.5:
        market_state = "HYPER-INFLATED"
        advice = "Market flush with capital. Avoid early bidding wars on Tier 1 Icons. Pivot to RTMs and mid-tier assets to force rivals to deplete capital."
    elif inflation_index < 3.5:
        market_state = "ILLIQUID (BEAR MARKET)"
        advice = "Global capital is dry. Aggressively target elite marquee players—franchises mathematically lack the liquidity to outbid you."

    # 4. Formulate Professional Output
    market_makers = []
    for m in team_metrics[:3]:
        # Professional Formatting: MI - ₹80.0Cr (₹10.0Cr/slot) | ⭐ 85.0
        market_makers.append(f"{m['team']} - ₹{m['purse']:.1f}Cr (₹{m['ppp']:.1f}Cr/slot) | ⭐{m['points']:.1f} PTS")

    distressed_assets = []
    for m in team_metrics[-3:]:
        # Identify teams facing Purse Breach or Base Price Traps
        if m['ppp'] < 1.5 and m['slots_left'] > 0:
            distressed_assets.append(f"{m['team']} - ₹{m['purse']:.1f}Cr (₹{m['ppp']:.1f}Cr/slot) | ⭐{m['points']:.1f} PTS")

    if not distressed_assets:
        distressed_assets.append("No franchises currently in critical distress.")

    insights = {
        "macro_economics": {
            "inflation_index": round(inflation_index, 2),
            "total_liquidity_cr": round(global_liquidity, 2),
            "market_state": market_state
        },
        "advice": advice,
        "leaders": market_makers,
        "desperate": distressed_assets
    }

    # 5. Atomic File Operations (100% Crash-Proof)
    output_file = os.path.join(data_dir, 'live_insights.json')
    temp_file = output_file + '.tmp'
    try:
        # Write to a temporary file first, then instantly swap it. 
        # This prevents the UI from trying to read a half-written JSON file.
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(insights, f, indent=4)
        os.replace(temp_file, output_file)
    except Exception:
        pass 

if __name__ == "__main__":
    generate_executive_insights()