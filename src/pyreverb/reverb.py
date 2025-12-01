import atexit
import os.path
import platform
import subprocess
import time
import uuid
from enum import Enum
from typing import Type, TypeVar

from .reverb_errors import *
from .reverb_kernel import *

T = TypeVar("T")

VERBOSE = 2
PATH_LOG = "./logs/server.log"
if platform.system() == "Windows":
    PATH_SHUTDOWN_FLAG = "%appdata%/pyreverb/"
elif platform.system() == "Linux":
    PATH_SHUTDOWN_FLAG = "/pyreverb/"
else:
    PATH_SHUTDOWN_FLAG = None


"""
- 2: Full verbose
- 1: Only some things
- 0: Stop verbosing
"""

AUTO_CLOSE = False
"""
Set to True to make the server closed if he see a shutdown.flag
"""


def handle_exit():
    """
    Trigger on exit
    """
    if ReverbManager.REVERB_SIDE == ReverbSide.SERVER and AUTO_CLOSE:
        save_logs(PATH_LOG)


atexit.register(handle_exit)


def check_for_shutdown_flag():
    """
    - rigger an exit on windows if the shutdown.flag is saw
    - Will not trigger any atexit event
    """
    while True and AUTO_CLOSE:
        time.sleep(1)
        if os.path.exists(f"{PATH_SHUTDOWN_FLAG}./shutdown.flag") and ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            print("Receiving a shutdown flag closing...")
            os.remove(f"{PATH_SHUTDOWN_FLAG}./shutdown.flag")
            save_logs()
            os._exit(0)


# Start the thread that checks a shutdown flag
threading.Thread(target=check_for_shutdown_flag, daemon=True).start()


class ReverbSide(Enum):
    SERVER = 1
    CLIENT = 2


class SyncVar:
    """
    Simple class that trigger a hook when the value changes and syncs var between all clients
    """

    def __init__(self, default=None, on_changed: list[staticmethod] = None):
        """
        :param default: The value
        :param on_changed: List of methode that will be trigger if the value that will be set changes
        """
        if on_changed is None:
            on_changed = []
        self.on_changed = on_changed
        self.value = default
        self.has_changed = False

    def get(self, val_if_not_found=None, get_only_if_change=False) -> object:
        """
        Get the value
        :param val_if_not_found: Default value that will be return if the value is None
        :param get_only_if_change: Will return None if the value is not previously change
        (Careful it is not really sync, it is just for Reverb)
        :return: The value
        """
        if get_only_if_change and not self.has_changed:
            return None
        return self.value if self.value else val_if_not_found

    def set(self, val):
        """
        Set a value
        :param val: The value
        """
        old = self.value
        self.value = val
        if old != val:
            self.has_changed = True
            for func in self.on_changed:
                func(old, val)


def start_distant(file, side: str, is_host=False, *args, **kwargs):
    """
    Sart a process of the game with his side.
    :param file: The name of the file to be executed
    :param side: The side to start
    :param is_host: Set to true if the client (and only for client) is the host
    :param args: More arguments
    :param kwargs: More dict arguments
    :return: The process
    """
    system = platform.system()
    if system == "Windows":
        subprocess.Popen([sys.executable, file, side, "1" if is_host else "0"] + list(args) + list(kwargs), creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif system == "Linux":
        terms = [
            ["gnome-terminal", "--"],
            ["konsole", "-e"],
            ["xterm", "-e"],
            ["qterminal", "-e"]
        ]
        for term in terms:
            try:
                subprocess.Popen(term + ["python3", file, side, "1" if is_host else "0"] + list(args) + list(kwargs))
                return
            except FileNotFoundError:
                continue
        raise RuntimeError(f"No terminal found: {[t[0] for t in terms]}")

    else:
        raise OSError("Unsupported OS!")
    return subprocess.Popen([sys.executable, file, side, "1" if is_host else "0"] + list(args) + list(kwargs))


def stop_distant_server():
    """
    Called to generate a shutdown.flag file to shut down the server if he is on a subprocess
    """
    open(f"{PATH_SHUTDOWN_FLAG}/shutdown.flag", "w").close()


def check_if_json_serializable(*args: SyncVar):
    for arg in args:
        try:
            json.dumps(arg)
        except (TypeError, OverflowError):
            raise Exception(
                f"The arg: {arg} is not serializable ! It has to be serializable by JSON to be agree as a reverb_args.")


class ReverbObject:
    """
    - Base class of all object connected to the Network
    """

    def __init__(self, *reverb_args: SyncVar, uid: str = "Unknown", belonging_membership: int = None):
        """
        :param reverb_args: All the custom vars
        :param uid: The uid of the object, let it on None if you are not sure of what you're doing here
        :param belonging_membership: This refers to the port of a client. With this you can know if the RO is from a local instance or not. Let it on None if you're not sure what you're doing here
        """
        self.belonging_membership = belonging_membership
        self.reverb_args = reverb_args
        self.uid: str = uid
        self.is_alive = True
        self.type = self.__class__.__name__
        self.is_initialized = False

    def get_sync_vars(self, get_value=False, get_only_if_changed=True) -> list[SyncVar | object]:
        """
        List all SyncVars initialized into the ReverbObject
        :param get_value: Will get the value of the SyncVar if True else will return the object
        :param get_only_if_changed: Get the value only if changed
        :return: A list of all SyncVars or val of the SyncVar
        """
        sync_vars = []
        for arg in list(self.__dict__.values())[:len(self.reverb_args)]:
            if isinstance(type(arg), type(SyncVar)):
                val = (arg.get(get_only_if_changed) if get_value else arg)
                sync_vars += ([val] if not get_only_if_changed else ([val] if arg.has_changed else []))
                if get_only_if_changed:
                    arg.has_changed = False
        return sync_vars

    def pack(self, only_syn_vars) -> list[object]:
        """
        :param only_syn_vars: If True, it does not return a type + belonging_membership but just sync_vars
        :return: A list of all necessary args that are linked between the server and the clients
        """
        sync_vars = self.get_sync_vars(get_value=True, get_only_if_changed=only_syn_vars)
        check_if_json_serializable(*sync_vars)

        # If not init yet: send the type and the belonging_membership to construct the object | if no sync vars pack nothing
        return ([self.type, self.belonging_membership] if not only_syn_vars else []) + (
            sync_vars if sync_vars != [] else [])

    def sync(self, *reverb_args):
        """
        - Call on the 'CLIENT' side to sync new ro data
        - Know that values into reverb_args will be applied to variable along the position into the init
        :param reverb_args: List of args to be updated
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            if reverb_args != ():
                for key, val in zip(self.__dict__, reverb_args):
                    getattr(self, key).set(val)
                self.reverb_args = reverb_args
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE.name)

    @staticmethod
    def print_object(msg):
        """
        - Print a message with the ReverbObject style
        :param msg: The message
        """
        print(f"{Back.MAGENTA + Fore.RED}[{Fore.RESET}REVERB_OBJECT{Fore.RED}]{Style.RESET_ALL} {msg}")

    def is_owner(self) -> bool:
        """
        - Chek if the ReverbObject is a membership of this client
        - Only call on the 'CLIENT' side
        :return:
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            return ReverbManager.REVERB_CONNECTION.client.getsockname()[1] == self.belonging_membership
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE)

    def compute_server(self, func, *args):
        """
        - Send a Packet to the server to compute a function server with args
        - Only on 'CLIENT' side
        :param func: The server function reference. Has to be into the Class
        :param args: Args of the function
        """
        if self.is_alive:
            ReverbManager.REVERB_CONNECTION.send("calling_server_computing", self.uid, func.__name__, *args)

    def compute_client(self, func, *args):
        """
        - Send a Packet to the client to compute a function client with args
        - Only on 'SERVER' side
        :param func: The client function reference. Has to be into the Class
        :param args: Args of the function
        """
        if self.is_alive:
            ReverbManager.REVERB_CONNECTION.send("calling_client_computing", self.uid, func.__name__, *args)

    def is_uid_init(self) -> bool:
        """
        :return: if uid is an init or not
        """
        return self.uid != "Unknown"

    def on_init_from_client(self):
        """
        - Call on the 'CLIENT' side
        - Override this function
        - Call when the object is creating from the 'Client' side
        """

    def on_init_from_server(self):
        """
        - Call on 'SERVER' side
        - Override this function
        - Call when the object is creating from the 'Server' side
        """

    def on_destroy_from_client(self):
        """
        - Call on the 'CLIENT' side
        - Override this function
        - Call when the object is removing from the 'CLIENT' side
        """

    def on_destroy_from_server(self):
        """
        - Call on 'SERVER' side
        - Override this function
        - Call when the object is removing from the 'SERVER' side
        """

    def __del__(self):
        if VERBOSE == 2:
            ReverbObject.print_object(f"Destroying the object {self.uid=}")


class ReverbManager:
    """
    - This class is static!
    - It links ReverbObject to the reference of the ReverbObject!
    """
    REVERB_SIDE: ReverbSide = None
    REVERB_CONNECTION: Client | Server = None  # Client, or Server
    REVERB_OBJECTS: dict[str, ReverbObject] = {}
    REVERB_OBJECT_REGISTRY = {"ReverbObject": ReverbObject}  # Register all type
    try:
        IS_HOST = sys.argv[2] == "1"
        """Set to true automatically if is_host param passed as param otherwise False"""
    except:
        IS_HOST = False  # Check if host

    @staticmethod
    def print_manager(msg):
        """
        - Print a message with the ReverbManager style
        :param msg: The message
        """
        if VERBOSE != 0:
            print(f"{Back.YELLOW + Fore.RED}[{Fore.RESET}REVERB_MANAGER{Fore.RED}]{Style.RESET_ALL} {msg}")

    @staticmethod
    def add_type_if_dont_exit(ro: type[ReverbObject]):
        try:
            ReverbManager.REVERB_OBJECT_REGISTRY[ro.__name__]
        except KeyError:
            ReverbManager.REVERB_OBJECT_REGISTRY[ro.__name__] = ro
            if VERBOSE >= 1:
                ReverbManager.print_manager(f"Adding type '{ro.__name__}' to the registry.")

    @staticmethod
    def server_sync():
        """
        - Call on 'SERVER' side
        - Sync value from 'SERVER' to 'CLIENT' side
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            ros = {}
            # Avoiding: "RuntimeError: dictionary changed size during iteration"
            for uid, ro in list(ReverbManager.REVERB_OBJECTS.items()):
                if ro != "DESTROYED":
                    pack = ro.pack(only_syn_vars=ro.is_initialized)
                    if pack:
                        ros[uid] = pack
                    if not ro.is_initialized:
                        ro.is_initialized = True

            ReverbManager.REVERB_CONNECTION.send_to_all("server_sync", ros)
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE)

    @staticmethod
    @server_event_registry.on_event("client_connection")
    def on_client_connect(clt: socket.socket, *args):
        """
        - 'Server' side
         - Spawn existent ro on the new client!
        """
        ros = {}
        for uid, ro in list(ReverbManager.REVERB_OBJECTS.items()):
            if ro != "DESTROYED":
                pack = ro.pack(only_syn_vars=False)
                if pack:
                    ros[uid] = pack
        ReverbManager.REVERB_CONNECTION.send_to(clt, "server_sync", ros)

    @staticmethod
    def get_reverb_object(uid: str) -> ReverbObject:
        """
        - Get the reverb object by uid
        :param uid: The uid
        :return: ReverbObject or ReverbObjectNotFoundError if not found
        """
        try:
            return ReverbManager.REVERB_OBJECTS[uid]
        except KeyError:
            raise ReverbObjectNotFoundError(uid)

    @staticmethod
    def get_cls_by_type_name(t: str):
        try:
            return ReverbManager.REVERB_OBJECT_REGISTRY[t]
        except KeyError:
            raise ReverbTypeNotFoundError(t)

    @staticmethod
    def get_all_ro_by_type(t: Type[T]) -> list[T]:
        """
        - Get all the ReverbObject by a type
        :param t: Type of ReverbObject
        :return: Return the list of all found same types into the ReverbManager
        """
        ros = []
        for uid, ro in ReverbManager.REVERB_OBJECTS.items():
            if ro != "DESTROYED":
                if isinstance(ro, t):
                    ros.append(ro)
        return ros

    def spawn_ro(self, ro: ReverbObject):
        """
        - Call on the 'Server' side
        - Instantiate a new ro in all clients
        :param ro: The ReverbObject that will be instantiated
        """
        self.add_new_reverb_object(ro)

    @staticmethod
    def add_new_reverb_object(ro: ReverbObject):
        """
        - Add a new ReverbObject to the ReverbManager
        :param ro: The ReverbObject
        """
        if ro not in ReverbManager.REVERB_OBJECTS.values():  # Check if the
            if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:  # check RM side
                if not ro.is_uid_init():  # Check if the RO is not init yet
                    # SERVER
                    uid = str(uuid.uuid4())
                    ReverbManager.REVERB_OBJECTS[uid] = ro
                    ro.uid = uid
                    threading.Thread(target=ro.on_init_from_server, daemon=True).start()
                else:
                    raise ReverbUIDAlreadyInitError(ro, ro.uid)
            else:
                # CLIENT
                if ro.is_uid_init():
                    ReverbManager.REVERB_OBJECTS[ro.uid] = ro
                    ro.is_initialized = True
                else:
                    raise ReverbUIDUnknownError()
                threading.Thread(target=ro.on_init_from_client, daemon=True).start()
        else:
            raise ReverbObjectAlreadyExistError(ro)
        if VERBOSE == 2:
            ReverbManager.print_manager(
                f"New ReverbObject: {ro} add into '{ReverbManager.REVERB_SIDE.name}' side with uid={ro.uid}")

    @staticmethod
    def remove_reverb_object(uid: str):
        """
        - Call on 'SERVER' side only
        - Remove the ro from all clients
        :param uid: The uid of the RO
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            try:
                ro: ReverbObject = ReverbManager.get_reverb_object(uid)
                ro.is_alive = False

                threading.Thread(target=ro.on_destroy_from_server, daemon=True).start()
                ReverbManager.REVERB_OBJECTS[uid] = "DESTROYED"
                f = lambda: (time.sleep(3), ReverbManager.REVERB_OBJECTS.pop(
                    uid))  # Remove the ro 3 sec after on the server to avoid syncing bugs
                threading.Thread(target=f, daemon=True).start()
            except KeyError:
                raise KeyError(f"The {uid=} is not found !")

            ReverbManager.REVERB_CONNECTION.send_to_all("remove_ro", uid)
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE)

    @staticmethod
    @client_event_registry.on_event("remove_ro")
    def on_server_remove_reverb_object(clt: socket.socket, uid, *args):
        """
        - Only call on 'CLIENT' side
        - Remove the object
        :param clt: The socket
        :param uid: The uid of the ReverbObject to delete
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            ro: ReverbObject = ReverbManager.get_reverb_object(uid)
            ro.is_alive = False
            ReverbManager.REVERB_OBJECTS.pop(uid)
            threading.Thread(target=ro.on_destroy_from_client(), daemon=True).start()
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE)

    @staticmethod
    @client_event_registry.on_event("server_sync")
    def on_server_sync(clt: socket.socket, ros: dict[str, list[list[object]]], *args):
        """
        - Called on the 'Client' side
        - Called when the server syncs the state of ReverbObject with clients
        :param clt: The client socket
        :param ros: Dict[uids: list[list(values)]]
        """
        for uid, ro_data in ros.items():
            ro: ReverbObject = None
            try:  # try to get a reverb_object
                ro = ReverbManager.get_reverb_object(uid)
            except ReverbObjectNotFoundError:  # create a new one
                t: str = ro_data[0]  # Type
                cls = ReverbManager.get_cls_by_type_name(t)  # Class
                args = ro_data[2:]  # arguments

                try:
                    ro = cls(*args, belonging_membership=ro_data[1])
                except TypeError:
                    raise TypeError(
                        f"Not enough param passed! You try to construct {cls} but those elements are passed {args}, {ro_data}")
                ro.uid = uid
                ReverbManager.add_new_reverb_object(ro)
                ro_data = ro_data[2:]
            ro.sync(*ro_data)

    @staticmethod
    @server_event_registry.on_event("calling_server_computing")
    def on_calling_server_computing(clt: socket.socket, uid: str, func_name: str, *args):
        """
        - Called on the 'Server' side
        - Called when a ReverbObject send data to be computed by the server (like movements, interactions, etc.)
        :param clt: The client socket
        :param uid: The uid of the ReverbObject
        :param func_name: The function name
        :param args: Params of the function
        """
        try:
            ro = ReverbManager.get_reverb_object(uid)
            if ro == "DESTROYED":
                return
        except ReverbObjectNotFoundError:
            warn(f"You try to compute on the server with a uid not found {uid=}.\n"
                 f"This may occur because the ro was removed and the syncing between the client and the server is not enough fast! or just because the uid is real2"
                 f"ly not found!")
            return

        try:
            func = getattr(ro, func_name)
            if args == ():
                func()
            else:
                func(*args)
        except AttributeError:
            raise NameError(f"The {func_name=} wasn't found into the ReverbObject!")

    @staticmethod
    @client_event_registry.on_event("calling_client_computing")
    def on_calling_client_computing(clt: socket.socket, uid: str, func_name: str, *args):
        """
        - Called on the 'Client' side
        - Called when a ReverbObject send data to be computed by the client
        :param clt: The socket
        :param uid: The uid of the ReverbObject
        :param func_name: The function name
        :param args: Params of the function
        """
        try:
            ro = ReverbManager.get_reverb_object(uid)
            if ro == "DESTROYED":
                return
        except ReverbObjectNotFoundError:
            warn(f"You try to compute on the client with a uid not found {uid=}.\n"
                 f"This may occur because the ro was removed and the syncing between the client and the server is not enough fast! or just because the uid is rea"
                 f"ly not found!")
            return

        try:
            func = getattr(ro, func_name)
            if args == ():
                func()
            else:
                func(*args)
        except AttributeError:
            raise NameError(f"The {func_name=} wasn't found into the ReverbObject!")

    @staticmethod
    def reverb_object_attribute(cls):
        """
        - Decorator of a ReverbObject class and add the type into the ReverbManager
        :param cls: The class
        :return: cls
        """
        if issubclass(cls, ReverbObject):
            ReverbManager.add_type_if_dont_exit(cls)
        else:
            raise TypeError(f"The class {cls} must be derivative from a ReverbObject!")
        return cls
