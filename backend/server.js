const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const fs = require('fs');
const path = require('path');
const cors = require('cors');
const { exec } = require('child_process');

const app = express();
app.use(cors());
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });

const DATA_DIR = path.join(__dirname, '../data');
const STATE_FILE = path.join(DATA_DIR, 'global_auction_state.json');
const SETTINGS_FILE = path.join(DATA_DIR, 'auction_settings.json');
const POINTS_DB_FILE = path.join(DATA_DIR, 'player_database.json');
const SCRIPT_FILE = path.join(__dirname, '../scripts/initialize_auction.py');

let memState = null;
let memDB = {};

function loadIntoMemory() {
    if (fs.existsSync(STATE_FILE)) memState = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    if (fs.existsSync(POINTS_DB_FILE)) memDB = JSON.parse(fs.readFileSync(POINTS_DB_FILE, 'utf8'));
}

function broadcastState() {
    if (memState) io.emit('auction_update', memState);
    if (Object.keys(memDB).length > 0) io.emit('database_update', memDB);
}

function norm(name) { return (name || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }

io.on('connection', (socket) => {
    loadIntoMemory();
    broadcastState();
    
    socket.on('start_auction', (settings) => {
        console.log("\n➤ [SYSTEM] BOOT SEQUENCE INITIATED...");
        if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
        fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 4));
        
        // THE FIX: Bulletproof Absolute Path Execution
        const command = `python "${SCRIPT_FILE}"`;
        console.log("➤ [ENGINE] Executing:", command);
        
        exec(command, (error, stdout, stderr) => {
            if (error) {
                console.error("❌ [FATAL ERROR] PYTHON ENGINE CRASHED!");
                console.error("DETAILS:", error.message);
                console.error("STDERR:", stderr);
                return; // Stop the boot process
            }
            if (stdout) console.log("➤ [PYTHON OUTPUT]:\n", stdout);
            
            console.log("✅ [SYSTEM] DATABASE BUILT. LAUNCHING DASHBOARD.");
            loadIntoMemory(); 
            broadcastState();
        });
    });

    socket.on('register_bid', (data) => {
        if (!memState || !memState.teams[data.team]) return;
        let pData = memDB[data.player] || { points: 75.0, role: "BAT", is_os: false };
        let cost = parseFloat(data.price);
        let team = memState.teams[data.team];

        team.budget_remaining -= cost;
        team.players_bought += 1;
        if (pData.is_os) team.overseas_bought += 1;
        
        let isRTM = false;
        if (team.rtm_cards && team.rtm_cards.map(norm).includes(norm(data.player))) {
            isRTM = true; team.rtms_used += 1; 
        }
        
        team.squad.push({ name: data.player, price: cost, points: pData.points, is_os: pData.is_os, role: pData.role, is_rtm: isRTM });
        fs.writeFile(STATE_FILE, JSON.stringify(memState, null, 4), () => {});
        broadcastState();
    });

    socket.on('end_auction', () => {
        [STATE_FILE, SETTINGS_FILE].forEach(f => { if(fs.existsSync(f)) fs.unlinkSync(f); });
        memState = null;
        io.emit('auction_ended');
    });
});

server.listen(4000, () => console.log("🚀 BIDBLAZE V11.5 SERVER ONLINE"));