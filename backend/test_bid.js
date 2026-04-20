const { io } = require("socket.io-client");
const socket = io("http://localhost:4000");

socket.on("connect", () => {
    console.log("🔌 Connected to server! Firing Mock Bid...");
    
    // We are simulating RCB buying Virat Kohli for 15.0 Cr
    socket.emit("register_bid", {
        team: "RCB",
        player: "Virat Kohli",
        price: 15.0
    });

    setTimeout(() => {
        console.log("🔨 Bid sent successfully. Closing test.");
        process.exit(0);
    }, 1000);
});