
<p align="center">
  <img src="src/pyreverb/assets/banner.png" alt="PyReverb Banner">
</p>

# PyReverb

[![PyPI version](https://img.shields.io/pypi/v/pyreverb.svg)](https://pypi.org/project/pyreverb/)
![License](https://img.shields.io/github/license/LeLaboDuGame/PyReverb)

PyReverb is a lightweight Python networking framework for real-time client–server synchronization of game and simulation objects.

It is designed to make it easy to:

- Define network-aware objects once, and use them on both server and client
- Keep object state synchronized across all peers
- Trigger remote actions using events and RPC-like calls
- Build fast multiplayer prototypes and real-time simulations

---

## Table of Contents

1. [Features](#features)  
2. [Why PyReverb](#why-pyreverb)  
3. [Installation](#installation)  
4. [Quick Start](#quick-start)  
   - [1. Define a networked object](#1-define-a-networked-object)  
   - [2. Minimal server](#2-minimal-server)  
   - [3. Minimal client](#3-minimal-client)  
5. [Event System](#event-system)  
6. [Project Structure](#project-structure)  
7. [Support](#support)  
8. [Contributing](#contributing)  
9. [License](#license)  
10. [Author](#author)

---

## Features

- **Object synchronization**  
  Define `ReverbObject` subclasses and keep their state in sync across the network.

- **Client–server framework**  
  Built-in `Server` and `Client` abstractions to manage connections and messaging.

- **Event-driven architecture**  
  Register callbacks on custom events (connect, disconnect, gameplay events, etc.).

- **Remote calls / actions**  
  Execute actions remotely between server and clients in a structured way.

- **Lightweight and focused**  
  Minimal external dependencies; integrates well with existing game loops (e.g. `pygame`).

---

## Why PyReverb

- **Game-oriented**: Designed with real-time games and interactive simulations in mind.  
- **Simple mental model**: Think in terms of objects and events, not raw sockets.  
- **Python-first**: Pure Python API that fits naturally into existing Python projects.  
- **Extensible**: You control how objects are created, synchronized, and updated.

Use it for:

- 2D/3D multiplayer games  
- Real-time collaborative tools  
- Networked simulations and visualizations  

---

## Installation

Requirements:

- Python **3.13+**
- `virtualenv` or another virtual environment tool (recommended)

Inside your virtual environment:
```
bash
git clone https://github.com/LeLaboDuGame/PyReverb.git
cd PyReverb

# Install dependencies for development / local use
pip install -r requirements.txt

# Or install as a package (editable for development)
pip install -e .
```
You can also install directly from source in another project:
```
bash
pip install git+https://github.com/LeLaboDuGame/PyReverb.git
```
---

## Quick Start

Below is a minimal end‑to‑end example showing:

1. How to define a synchronized object
2. How to start a server
3. How to connect a client

> The code is written as if you split it into three files: `shared_objects.py`, `server.py`, and `client.py` inside your project.

### 1. Define a networked object
```
python
# shared_objects.py
from pyreverb.reverb import ReverbManager, ReverbSide, ReverbObject

# Decide which side you're currently defining for.
# This file can be imported by both client and server.
ReverbManager.REVERB_SIDE = ReverbSide.SERVER  # or CLIENT when imported by the client


@ReverbManager.reverb_object_attribute
class Player(ReverbObject):
    def __init__(self, pos=(0, 0), uid=None, add_on_init=True):
        # Local attributes that will be synchronized
        self.pos = list(pos)
        super().__init__(uid=uid, add_on_init=add_on_init)

    def on_init_from_server(self):
        # Called when the Player is created on the server
        print(f"[SERVER] Player {self.uid} initialized at {self.pos}")

    def on_init_from_client(self):
        # Called when the Player appears on a client
        print(f"[CLIENT] Player {self.uid} spawned at {self.pos}")
```
### 2. Minimal server
```
python
# server.py
from pyreverb.reverb import ReverbManager, ReverbSide, Server
from shared_objects import Player  # noqa: F401 - ensure class is registered


def main():
    # Configure PyReverb as server-side
    ReverbManager.REVERB_SIDE = ReverbSide.SERVER

    server = Server()
    ReverbManager.REVERB_CONNECTION = server

    # Start listening for clients
    server.start_server()

    # Create a player instance on the server
    player = Player(pos=(5, 5))
    print(f"[SERVER] Created Player with uid={player.uid}")

    # Main loop placeholder (replace with your game loop)
    try:
        while True:
            # Process network events / messages
            server.update()
            # ... your game logic, physics, etc. ...
    except KeyboardInterrupt:
        print("[SERVER] Shutting down...")
        server.stop_server()


if __name__ == "__main__":
    main()
```
### 3. Minimal client
```
python
# client.py
from pyreverb.reverb import ReverbManager, ReverbSide, Client
from shared_objects import Player  # noqa: F401 - ensure class is registered


def main():
    # Configure PyReverb as client-side
    ReverbManager.REVERB_SIDE = ReverbSide.CLIENT

    client = Client()
    ReverbManager.REVERB_CONNECTION = client

    # Connect to the server (adjust host/port if needed)
    client.connect(host="127.0.0.1", port=5555)

    # Main loop placeholder (replace with your render / game loop)
    try:
        while True:
            client.update()
            # Here you would update local input and send changes, e.g.:
            # for player in Player.get_all_instances():
            #     player.pos[0] += 1  # move right, for example
    except KeyboardInterrupt:
        print("[CLIENT] Disconnecting...")
        client.disconnect()


if __name__ == "__main__":
    main()
```
**How this works:**

- The `Player` class is registered as a networked object via `@ReverbManager.reverb_object_attribute`.
- The server creates a `Player` instance; PyReverb synchronizes it with connected clients.
- The client keeps a local mirror of the `Player` instance and can react to updates in its callbacks.

For more advanced usage (multiple object types, more complex logic, etc.), you can follow the same pattern with additional `ReverbObject` subclasses.

---

## Event System

PyReverb uses an event-driven core so that you can react to network events without constantly polling everything manually.

A simplified usage pattern looks like this:
```
python
from pyreverb.reverb import ReverbManager

kernel = ReverbManager.get_kernel()

@kernel.on_event("client_connected")
def on_client_connected(client_id):
    print(f"Client connected: {client_id}")

@kernel.on_event("client_disconnected")
def on_client_disconnected(client_id):
    print(f"Client disconnected: {client_id}")
```
You can define and emit custom events to coordinate gameplay logic, lobby systems, or other high‑level behaviors above the raw networking layer.

---

## Project Structure

At a high level, the repository is organized as follows:

- `src/pyreverb/` – Core library code  
- `src/pyreverb/assets/` – Assets such as the README banner  
- `src/pyreverb/Exemple/` – Example project demonstrating PyReverb in action  
- `pyproject.toml` – Packaging configuration  
- `README.md` – Project documentation (this file)  

You can use the example project as a reference when integrating PyReverb into your own game or simulation.

---

## Support

- Open an **Issue** on the repository for bugs or feature requests.  
- Use **Discussions** (if enabled) for general questions and design ideas.  
- Check the source and examples for reference implementations.

---

## Contributing

Contributions are welcome.

1. Open an issue to discuss new features or changes.  
2. Fork the repository and create a feature branch:  
   ```bash
   git checkout -b feature/my-feature
   ```  
3. Implement your changes and add tests or example usage where appropriate.  
4. Ensure code style and formatting are consistent.  
5. Open a Pull Request with a clear description of what you changed and why.

---

## License

This project is licensed under the **Apache License 2.0**.  
See the [LICENSE](LICENSE) file for the full license text.

---

## Author

PyReverb is maintained by **LeLaboDuGame** (Twitch: https://twitch.tv/LaboTTV). <br>
For more information and updates, see the project homepage:

- GitHub: https://github.com/LeLaboDuGame/PyReverb

