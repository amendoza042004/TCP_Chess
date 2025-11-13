#!/usr/bin/env python3
import socket
import json
import sys
import threading

sys.stdout.reconfigure(line_buffering=True)

def send(sock, obj):
    try:
        sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
    except:
        print("[error] failed to send")
        sys.exit(1)

def recv_loop(sock):
    f = sock.makefile("r")
    for line in f:
        try:
            msg = json.loads(line.strip())
        except:
            continue
        handle_message(msg)

def handle_message(msg):
    t = msg.get("type")

    if t == "welcome":
        print("[server] welcome message received")
    elif t == "queued":
        print(f"[server] queued (position {msg['pos']})...")
    elif t == "start":
        print(f"[server] Game started — you are {msg['color'].upper()} vs {msg['opponent']}")
    elif t == "state":
        print(f"[server] Turn: {msg['turn']} | FEN: {msg['fen']}")
    elif t == "move_ok":
        print(f"[server] Move accepted: {msg['uci']} by {msg['by']}")
    elif t == "illegal":
        print(f"[server] Illegal move: {msg['reason']}")
    elif t == "chat":
        print(f"[chat] {msg['from']}: {msg['text']}")
    elif t == "result":
        print(f"[server] Game over — {msg['outcome']}, winner = {msg.get('winner')}")
    elif t == "opponent_left":
        print("[server] Opponent left — you win by forfeit")
    else:
        print("[server]", msg)

def main():
    if len(sys.argv) != 3:
        print("Usage: python chess_client.py <server-ip> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # Expect welcome from server
    send(sock, {"type": "hello", "name": input("Enter name: ").strip()})

    threading.Thread(target=recv_loop, args=(sock,), daemon=True).start()

    while True:
        cmd = input("> ").strip()

        if cmd.startswith("move "):
            _, mv = cmd.split(" ", 1)
            send(sock, {"type": "move", "uci": mv})
        elif cmd.startswith("chat "):
            _, text = cmd.split(" ", 1)
            send(sock, {"type": "chat", "text": text})
        elif cmd == "resign":
            send(sock, {"type": "resign"})
        elif cmd == "quit":
            send(sock, {"type": "quit"})
            print("Disconnected.")
            break
        else:
            print("Commands:")
            print("  move e2e4")
            print("  chat hello")
            print("  resign")
            print("  quit")

if __name__ == "__main__":
    main()

