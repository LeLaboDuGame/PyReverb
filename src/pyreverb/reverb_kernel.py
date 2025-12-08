import datetime
import json
import os
import re
import socket
import struct
import sys
import threading
from io import StringIO
from json import JSONDecodeError
from warnings import warn

from colorama import Fore, Back, Style


class Tee:
    """Store the console"""
    ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

    def __init__(self, *streams, log_buffer=None):
        self.streams = streams
        self.log_buffer = log_buffer or StringIO()
        self._buffer = ""

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()
        clean_data = Tee.ANSI_ESCAPE.sub('', data)

        self._buffer += clean_data
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            timestamp = datetime.datetime.now().strftime('%H:%M:%S:%f')
            self.log_buffer.write(f"[{timestamp}] | {line}\n")
            self.log_buffer.flush()

    def flush(self):
        # Pour finir la dernière ligne si pas de \n
        if self._buffer:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S:%f')
            self.log_buffer.write(f"[{timestamp}] | {self._buffer}\n")
            self.log_buffer.flush()
            self._buffer = ""
        for s in self.streams:
            s.flush()


# Storing output into a buffer
log_buffer = StringIO()
sys.stdout = Tee(sys.__stdout__, log_buffer=log_buffer)
sys.stderr = Tee(sys.__stderr__, log_buffer=log_buffer)


def save_logs(path: str = "./logs/"):
    file_path = f"{path}/log-{datetime.datetime.now().strftime('%y-%m-%d-%H-%M-%S')}.log"

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    print("Saving logs from this process...")
    with open(file_path, "w", encoding="utf-16") as log_file:
        log_file.write(log_buffer.getvalue())
        log_file.write(
            "\n\n\nDue to the stoping of the distant server (if it is the case), sometime logs can have error at the end!\n"
            "It is normal because when the server stop some threads are continuously opened.\n"
            "Closed the server make them crash! BUT IT IS NORMAL (normally normal it depends sometimes it is bad xd)\n"
            "Nevertheless examined them is a good things (you can have real errors!)")
        log_file.close()
    print("Log saved!")


class EventRegistry:
    """
    A Class that store events and handle them!
    """

    def __init__(self):
        self._events = {}

    def add_event(self, func, event_name):
        """
        Add an event to the EventRegistry
        :param func: The function
        :param event_name: The name of the event
        """
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(func)

    def on_event(self, event_name):
        """
        Simple decorator to trigger events
        :param event_name: The name of the event
        :return: The decorator
        """

        def decorator(func):
            self.add_event(func, event_name)
            return func

        return decorator

    def get(self, event_name):
        """
        Get an event by his name
        :param event_name: The name of the event
        :return: Event functions
        """
        return self._events.get(event_name)

    def trigger(self, event_name, sock, *args, threading_event=True):
        """
        Trigger an event
        :param sock: the reference of the outcoming socket packet's
        :param event_name: The name of the event
        :param threading_event: If true, it will handle the event into a new thread else it will just execute the event into the main thread
        """
        handlers = self._events.get(event_name, [])  # Check if the event name contains functions or not
        if handlers:
            for handler in handlers:
                try:
                    if threading_event:
                        threading.Thread(target=handler, args=(sock, *args), daemon=True).start()
                    else:
                        handler(sock, *args)
                except TypeError:
                    if threading_event:
                        threading.Thread(target=handler, args=sock, daemon=True).start()
                    else:
                        handler(sock)
        else:
            warn(f"The handler for '{event_name}' is not found ! It may be normal, ignore then.")

    def all_events(self):
        """
        :return: All events
        """
        return list(self._events.keys())


client_event_registry = EventRegistry()
server_event_registry = EventRegistry()


class Packet:
    """
    Manager of packets
    """

    @staticmethod
    def create_packet(name: str, *content):
        """
        Create a packet and encode it
        :param name: Name of the packet/event
        :param content: The contents to send
        :return: An encoded packet ready to be sent :)
        """
        return json.dumps({"name": name, "contents": content}).encode()

    @staticmethod
    def recv_exact(sock: socket.socket, n: int):
        data = b""
        try:
            while len(data) < n:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    raise ConnectionError("The socket is close...")
                data += chunk
            return data
        except ConnectionAbortedError:
            return b""

    @staticmethod
    def decode_packet(packet: bytes):
        """
        Decode the packet from a byte
        :param packet: The encoded packet
        :return: The name/event and the contents
        """
        try:
            decoded_packet = json.loads(packet.decode())
            return decoded_packet["name"], decoded_packet["contents"]
        except JSONDecodeError:
            warn(f"An error occurred with this packet: {packet.decode()}")
        except KeyError:
            warn(f"The packet is not valid ! A valid packet must have a 'name' and a 'contents' argument !")


class Client:
    """
    - A class that connect to a Server
    """

    def __init__(self, ip="127.0.0.1", port=8080):
        """
        :param ip: Ip server's
        :param port: Port server
        """
        self.port = port
        self.ip = ip
        self.client: socket.socket = None
        self.is_connected = False

    def connect(self):
        """
        Call to connect to the server
        """
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((self.ip, self.port))
            self.is_connected = True

            threading.Thread(target=self.listen, daemon=True).start()
            client_event_registry.trigger("connection", self.client)  # Trigger connection event
        except ConnectionRefusedError:
            Client.print_client("The server is unreachable !")
        except socket.gaierror:
            Client.print_client("Error with host name or IP unfound")
        except TimeoutError:
            Client.print_client("Connexion TimeOut !")

    def listen(self):
        """
        Thread that listens for new content from the server
        """
        try:
            while self.is_connected:
                try:
                    raw_len = Packet.recv_exact(self.client, 4)  # Get the length of the packet
                    length = struct.unpack("!I", raw_len)[0]
                    packet = Packet.recv_exact(self.client, length)
                    if packet:
                        packet_name, contents = Packet.decode_packet(packet)
                        if packet_name == "server_stop":
                            client_event_registry.trigger(packet_name, self.client,
                                                          *contents)  # Trigger the event linked to the message of the server
                            Client.print_client("Server stopped !")
                            break
                        client_event_registry.trigger(packet_name, self.client,
                                                      *contents)  # Trigger the event linked to the message of the server
                    else:
                        Client.print_client("The server send an empty packet ! Closing...")
                        break
                except ConnectionResetError:
                    Client.print_client("Connection lost !")
                    break
                except Exception as e:
                    if self.is_connected:
                        raise Exception(f"THIS IS NOT NORMAL:\n{e}")

        finally:
            self.disconnect()

    def send(self, packet_name: str, *content):
        """
        Send a content to the server
        :param packet_name: The name of the packet
        :param content: contents
        """
        if self.is_connected:
            packet = Packet.create_packet(packet_name, *content)
            length = len(packet)
            header = struct.pack('!I', length)
            try:
                self.client.sendall(header + packet)
            except BrokenPipeError:
                warn("The client has been disconnected during a sending operation!")
            except ConnectionResetError:
                warn("Server close or client disconnected during a sending operation!")
            except Exception as e:
                if self.is_connected:
                    raise Exception(f"THIS IS NOT NORMAL DURING A SEND OPERATION:\n{e}")

    def disconnect(self):
        """
        Call to disconnect the user
        """
        if self.is_connected:
            try:
                self.send("client_disconnection", self.client.getpeername())
            finally:
                self.is_connected = False
                client_event_registry.trigger("disconnection", self.client)
                Client.print_client("Client close and disconnect from the server !")
                self.client.close()  # Close the client

    @staticmethod
    def print_client(msg):
        """
        Print a message with client style
        :param msg: the message to print
        """
        print(f"{Back.BLUE + Fore.RED}[{Fore.RESET}CLIENT{Fore.RED}]{Style.RESET_ALL} {msg}")


class Server:
    """
    - A class that open a Server
    """

    def __init__(self, host="", port=8080, ):
        """
        :param host: The ip. Let it him by default
        :param port: The listen port!
        """
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_online = False
        self.clients: dict[tuple[str, int], socket.socket] = {}

    @staticmethod
    def print_server(msg):
        """
        Print a message with server style
        :param msg: the message to print
        """
        print(f"{Back.GREEN + Fore.RED}[{Fore.RESET}SERVER{Fore.RED}]{Style.RESET_ALL} {msg}")

    def start_server(self):
        """
        Start the server
        """
        Server.print_server("Starting server...")
        self.server.bind(("", self.port))
        self.server.listen()

        Server.print_server(f"Server online ! Waiting for clients on {self.host}:{self.port}...")
        self.is_online = True
        threading.Thread(target=self._accept_clients, daemon=True).start()

    def stop_server(self):
        """
        Stop the server
        """
        self.is_online = False
        packet = Packet.create_packet("server_stop")
        clts = list(self.clients.values())  # To avoid bugs
        for client in clts:
            client.send(packet)
            Server.print_server(f"The client: {client.getpeername()} is disconnect !")
            client.close()
        Server.print_server("All clients disconnected.")

        if self.server:
            self.server.close()
        Server.print_server("Server closed !")

    def _accept_clients(self):
        """Thread that accepts clients when they connect to the server"""
        try:
            while self.is_online:
                client_socket, addr = self.server.accept()
                self.clients[addr] = client_socket
                server_event_registry.trigger("client_connection", client_socket)
                threading.Thread(target=self._handle_client, args=(client_socket, addr), daemon=True).start()
        except KeyboardInterrupt:
            self.stop_server()
        except OSError:
            pass
        finally:
            Server.print_server("Server stop listening to new clients !")

    def _handle_client(self, client_socket, addr):
        """Thread that triggers event from packet recv from clients"""
        while self.is_online:
            try:
                raw_len = Packet.recv_exact(client_socket, 4)  # Get the length of the packet
                length = struct.unpack("!I", raw_len)[0]
                packet = Packet.recv_exact(client_socket, length)
                if packet:
                    packet_name, contents = Packet.decode_packet(packet)

                    if packet_name == "client_disconnection":
                        server_event_registry.trigger(packet_name, client_socket, *contents, threading_event=False)
                        break
                    else:
                        server_event_registry.trigger(packet_name, client_socket, *contents)
                else:
                    Server.print_server(
                        f"A packet from: {addr} has been send with no data ! This is illegal closing the listening thread and the communication !")
                    break
            except ConnectionResetError:
                server_event_registry.trigger("client_disconnection", client_socket, threading_event=False)
                Server.print_server(f"The client at address: {addr} has been disconnected ! This is an anomaly.")
                break
            except Exception as e:
                if self.is_online:
                    print(f"THIS IS NOT NORMAL: {e}")

        if addr in self.clients:
            self.clients.pop(addr)
        client_socket.close()
        Server.print_server(f"The client: {addr} is disconnect !")

    def send_to_all(self, packet_name, *contents):
        """
        Send a packet to all player
        :param packet_name: The name of the packet/event
        :param contents: Contents
        """
        for client in self.clients.values():
            self.send_to(client, packet_name, *contents)

    @staticmethod
    def send_to(clt: socket.socket, packet_name, *contents):
        packet = Packet.create_packet(packet_name, *contents)
        length = len(packet)
        header = struct.pack('!I', length)
        try:
            clt.sendall(header + packet)
        except BrokenPipeError:
            warn(f"The client was disconnect during a sending operation: {clt.getpeername()}")
        except OSError:
            warn("The server is certainly closed...")
        except ConnectionResetError:
            warn(f"A client was disconnect during a sending operation!")


# Basic Event Registry

# SERVER EVENTS
@server_event_registry.on_event("client_disconnection")
def on_client_disconnect(clt, *args):
    Server.print_server(f"The client: {clt.getpeername()} disconnect itself ! (Client Side)")


@server_event_registry.on_event("client_connection")
def on_client_connect(clt, *args):
    Server.print_server(f"Client connected on: {clt.getpeername()} !")


# CLIENT EVENTS
@client_event_registry.on_event("connection")
def on_connection(clt, *args):
    Client.print_client("Client is connecting !")


@client_event_registry.on_event("disconnection")
def on_disconnection(clt, *args):
    Client.print_client("Client disconnecting.")
