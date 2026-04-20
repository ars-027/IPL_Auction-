import json
import os
import time

def get_top7_points(squad):
    """Calculates the true Top 7 points according to the official Bidblaze rules"""
    counts = {'BAT': 0, 'BOWL': 0, 'WK': 0, 'AR': 0}
    os_count = 0
    total_points = 0
    
    # Sort by highest points first
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
        
        # Enforce 3-2-1-1 and Overseas limits
        if counts[r] < rules[r]:
            if is_os and os_count >= 3:
                continue # Skip if it breaches the OS limit
            counts[r] += 1
            if is_os:
                os_count += 1
            total_points += p.get('points', 0)
            
    return total_points

def generate_live_insights():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    state_file = os.path.join(data_dir, 'global_auction_state.json')

    state = None
    # Safe read with retry mechanism to bypass Node.js file locks
    for _ in range(5):
        try:
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                break
        except json.JSONDecodeError:
            time.sleep(0.1) # File is currently being written by Node, wait.
        except Exception:
            time.sleep(0.1)

    # Abort safely if the file isn't ready
    if not state or 'teams' not in state: 
        return

    target_size = int(state.get('user_settings', {}).get('target_squad_size', 14))
    metrics = []

    for team, data in state['teams'].items():
        bought = data.get('players_bought', 0)
        slots = target_size - bought
        purse = data.get('budget_remaining', 0.0)
        
        # Prevent Division by Zero if squad is full
        power = (purse / slots) if slots > 0 else 0
        
        # Calculate points dynamically using the Top 7 Rulebook Engine
        squad = data.get('squad', [])
        points = get_top7_points(squad)

        metrics.append({
            "team": team, 
            "power": power, 
            "purse": purse, 
            "points": points
        })

    # Sort richest to poorest based on purchasing power
    metrics.sort(key=lambda x: x['power'], reverse=True)
    
    # REQUIREMENT 3: Format -> Team Name - Purse - Points (Using .1f for precise score tracking)
    rich = [f"{m['team']} - ₹{m['purse']:.2f}Cr - {m['points']:.1f} pts" for m in metrics[:3]]
    
    # Identify desperate teams (Averaging less than 2.0 Cr per remaining slot)
    broke = [f"{m['team']} - ₹{m['purse']:.2f}Cr - {m['points']:.1f} pts" for m in metrics[-3:] if m['power'] < 2.0]

    insights = {
        "market_state": "STABLE" if len(broke) < 3 else "VOLATILE",
        "advice": "Monitor the top bidders; they have the financial leverage to dictate base prices.",
        "leaders": rich,
        "desperate": broke
    }

    # Safe write to prevent UI flickering
    output_file = os.path.join(data_dir, 'live_insights.json')
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(insights, f, indent=4)
    except Exception:
        pass 

if __name__ == "__main__":
    generate_live_insights()