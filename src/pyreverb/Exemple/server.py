import socket

import pygame.time

from pyreverb.Exemple.shooter_objects import Player, TICK
from pyreverb.reverb import ReverbManager, ReverbSide
from pyreverb.reverb_kernel import server_event_registry, Server

clock = pygame.time.Clock()


@server_event_registry.on_event("client_connection")
def on_connecting(clt: socket.socket, *args):
    ReverbManager.add_new_reverb_object(
        Player(pos=[400, 400], color=Player.choose_rnd_color(), belonging_membership=clt.getpeername()[1]))


@server_event_registry.on_event("client_disconnection")
def on_disconnecting(clt: socket.socket, *args):
    for p in ReverbManager.get_all_ro_by_type(Player):
        if p.belonging_membership == clt.getpeername()[1]:
            ReverbManager.remove_reverb_object(p.uid)


def start_server():
    print("Starting server...")
    ReverbManager.REVERB_SIDE = ReverbSide.SERVER
    serv = Server()
    ReverbManager.REVERB_CONNECTION = serv
    serv.start_server()
    while True:
        try:
            clock.tick(TICK)
            ReverbManager.server_sync()
        except KeyboardInterrupt:
            serv.stop_server()
            break


if __name__ == "__main__":
    print("Starting server from main!")
    start_server()
