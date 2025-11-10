<p align="center">
  <img src="assets/banner.png" alt="PyReverb Banner">
</p>

# PyReverb

[![Version](https://img.shields.io/badge/version-1.0.3-blue)]()
![License](https://img.shields.io/github/license/LeLaboDuGame/PyReverb)

A lightweight Python networking framework for real-time client-server synchronization of objects, designed for multiplayer game development and interactive simulations.

---

## Table of Contents
1. [What the Project Does](#what-the-project-does)  
2. [Why the Project Is Useful](#why-the-project-is-useful)  
3. [Getting Started](#getting-started)  
   - [Prerequisites](#prerequisites)  
   - [Installation](#installation)  
4. [Usage Example](#usage-example)  
5. [Support](#support)  
6. [Contributing](#contributing)  
7. [License](#license)  
8. [About](#about)

---

## What the Project Does
PyReverb enables you to create network-synchronized objects across server and clients in Python.

**Key features:**
- Event-driven networking with automatic packet handling  
- Simple definition and synchronization of `ReverbObject` instances  
- Remote function execution between server and clients  
- Built-in registry for managing object types and instances efficiently

Ideal for:
- Multiplayer games  
- Real-time simulations  
- Collaborative interactive applications

---

## Why the Project Is Useful
- **Real-time synchronization** of objects  
- **Event-driven** architecture (connect, disconnect, custom events)  
- **Lightweight & extensible** (minimal dependencies)  
- **Flexible client/server design**  
- **Simplified networking** (no need to manage sockets manually)

---

## Getting Started

### Prerequisites
- Python 3.x  
- pip  
- Dependencies in `requirements.txt`

### Installation
```bash
git clone https://github.com/LeLaboDuGame/PyReverb.git
cd PyReverb
pip install -r requirements.txt
````

### Running the example

```bash
python Game.py
```

---

## Usage Example

```python
from reverb import ReverbManager, ReverbSide, ReverbObject, Client, Server

# On the server side:
ReverbManager.REVERB_SIDE = ReverbSide.SERVER

@ReverbManager.reverb_object_attribute
class Player(ReverbObject):
    def __init__(self, pos=[0,0], uid=None, add_on_init=True):
        self.pos = pos
        super().__init__(pos, uid=uid, add_on_init=add_on_init)

    def on_init_from_client(self):
        print("Player initialized on client")

    def on_init_from_server(self):
        print("Player initialized on server")

server = Server()
ReverbManager.REVERB_CONNECTION = server
server.start_server()

# On the client side:
ReverbManager.REVERB_SIDE = ReverbSide.CLIENT
client = Client()
ReverbManager.REVERB_CONNECTION = client
client.connect()
```

---

## Support

* Open an **Issue** for bugs or feature requests
* Start a **Discussion** for questions
* Check the `docs/` folder for documentation and API reference

---

## Contributing

Contributions are welcome!

1. Open an **Issue** to discuss the idea
2. Fork the repo & create a branch (`feature/my-feature`)
3. Submit a **Pull Request**
4. Add tests and documentation if possible
5. Keep coding style consistent

---

## License

This project is licensed under the **Apache License 2.0**.
See the [LICENSE](LICENSE) file for details.

---

## About

Just a simple repo to implement a server for games in Python.
Created by **LeLaboDuGame**.


