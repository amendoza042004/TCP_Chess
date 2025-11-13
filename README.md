# ♟️ TCP_Chess  
A two-player online chess game built using **Python**, **TCP sockets**, and a **Pygame GUI**.

---

## 📌 Features
- ✔️ Fully functional two-player chess over TCP  
- ✔️ Custom server-side chess logic for legal move validation  
- ✔️ Clean Pygame GUI with draggable pieces  
- ✔️ Unicode chess pieces (no external images needed)  
- ✔️ Right-hand move history sidebar  
- ✔️ Illegal move popup feedback  
- ✔️ Quit Game button  
- ✔️ Detects opponent disconnect (forfeit win)

---

## 📁 Project Structure

```
TCP_Chess/
│── chess_server.py   # Handles connections, game pairing, and state updates
│── chess_logic.py    # Full custom chess rules and move validation
│── chess_gui.py      # Pygame GUI client for players
│── README.md         # Documentation
```
---

## 🚀 How to Run

### 1️⃣ Install dependencies
It is recommended to use a virtual environment.

  python3 -m venv venv
  
  source venv/bin/activate   # macOS / Linux
  
  venv\Scripts\activate      # Windows

Install pygame:
  pip install pygame

2️⃣ Start the server
Run the server in a terminal:
  python3 chess_server.py

You should see:
Server listening on port 5002

3️⃣ Start two clients
Open two separate terminals and run:
  python3 chess_gui.py
Each client enters a name → the server automatically pairs them.

🎮 Game Controls
  Drag and drop pieces to make moves
  Illegal moves trigger an on-screen popup
  Move list appears in the right sidebar
  Click Quit Game to resign
When your opponent disconnects, you win by forfeit

🧩 Requirements
  Python 3.10 or newer
  pygame 2.6 or newer


