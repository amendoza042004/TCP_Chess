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

## 1️⃣ Install Dependencies

It is recommended to use a virtual environment.

### Create and activate a virtual environment
```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Install Pygame
```bash
pip install pygame
```

---

## 2️⃣ Start the Server

Run the server in a terminal:

```bash
python3 chess_server.py
```

You should see:

```
Server listening on port 5002
```

---

## 3️⃣ Start Two Clients

Open **two separate terminals**, and run:

```bash
python3 chess_gui.py
```

Each client enters a name →  
The server **automatically pairs** the two players into a game.

---

## 🎮 Game Controls

- **Drag and drop** pieces to make moves  
- **Illegal moves** trigger an on-screen popup  
- **Move list** appears in the right sidebar  
- **Quit Game** at any time using the quit button  
- If your opponent disconnects, **you win by forfeit**

---

## 🧩 Requirements

- **Python 3.10+**  
- **pygame 2.6+**

