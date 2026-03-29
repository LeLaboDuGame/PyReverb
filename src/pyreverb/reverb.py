import atexit
import platform
import random
import subprocess
import uuid
import warnings
from enum import Enum
from typing import Type, TypeVar, Any, Generic, Callable, List

from .reverb_errors import *
from .reverb_kernel import *

T = TypeVar("T")

VERBOSE = 2
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_LOG = f"{WORKING_DIR}/logs/"

"""
- 2: Full verbose
- 1: Only some things
- 0: Stop verbosing
"""


class ReverbSide(Enum):
    SERVER = 1
    CLIENT = 2


def start_distant(file, *args, **kwargs) -> subprocess.Popen:
    """
    Sart a process of the game with his side.
    :param file: The name of the file to be executed
    :param args: More argues
    :param kwargs: More dict arguments
    :return: The process
    """
    system = platform.system()
    if system == "Windows":
        print("Starting distant file on Windows")
        return subprocess.Popen([sys.executable, file] + list(args) + list(kwargs),
                                creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif system == "Linux":
        terms = [
            ["qterminal", "-e"],
            ["gnome-terminal", "--"],
            ["konsole", "-e"],
            ["xterm", "-e"],
        ]
        for term in terms:
            try:
                return subprocess.Popen(term + ["python3", file] + list(args) + list(kwargs))
            except FileNotFoundError:
                continue
        raise RuntimeError(f"No terminal found: {[t[0] for t in terms]}")

    else:
        raise OSError("Unsupported OS!")


def stop_subprocess(sub: subprocess.Popen = None):
    """
    Stop a process
    DON'T SAVE LOG IF SERVER IS CLOSED ON WINDOWS WITH THIS METHODE!!!
    :param sub: The subprocess
    """
    if sub and sub.poll() is None:
        sub.terminate()
        sub.wait()
        print("Server Closed!")
    else:
        warn(
            "You try to stop the process with a None subprocess! By default the subprocess is reverb.SERVER_PROCESS, set it to the server process before run it again if args is let by default.")


class SyncVar(Generic[T]):
    """
    A simple class that manage the value of synchronous variable
    """
    def __init__(self, default: T, on_changed: list[Callable[[T, T], None]] = None):
        """
        :param default: The default value
        :param on_changed: A list of callable function that are called when the value changed.
        """
        if on_changed is None:
            on_changed = []
        self.on_changed: list[Callable[[T, T], None]] = on_changed
        self._value: T = default

    @property
    def value(self) -> T:
        """
        :return: Get the value.
        """
        return self._value

    @value.setter
    def value(self, new_value: T):
        """
        Set the value
        :param new_value: the new value
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:

            if self.check_if_json_serializable(new_value):
                if new_value != self._value:
                    old = self._value
                    self._value = new_value

                    for func in self.on_changed:
                        func(old, self._value)

            else:
                warnings.warn(f"You tried to set a type that is not json serializable! {new_value=} actual_val={self.value=}")
        else:
            warnings.warn(f"You are trying to set the value of {self.__repr__()} on a 'Client' Side !")

    @staticmethod
    def check_if_json_serializable(val) -> bool:
        """
        Check if it can be json serializable
        :param val: The value
        :return: True if serializable
        """
        try:
            json.dumps(val)
            return True
        except (TypeError, OverflowError):
            return False

    def __repr__(self):
        return f"SyncVar[{type(self._value).__name__}](value={self._value})"

    def __str__(self):
        return self.__repr__()

print(SyncVar("This is an amazing SyncVar!"))
class ReverbObject:
    """
    - Base class of all object connected to the Network
    """

    def __init__(self, init_args: list[Any], sync_vars: dict[str, SyncVar] = None, uid: str = "Unknown", belonging_membership: int = None):
        """
        :param init_args: A list containing all the value needed to instantiate the constructor. Values need to be json serializable!
        :param sync_vars: A dict containing the name of the attribute of the SyncVar and his associate SyncVar
        :param uid: The uid of the object, let it on None if you are not sure of what you're doing here
        :param belonging_membership: This refers to the port of a client. With this you can know if the RO is from a local instance or not. Let it on None if you're not sure what you're doing here
        """
        if sync_vars is None:
            sync_vars = {}

        if init_args is None:
            init_args = []

        self.init_args = init_args
        self.belonging_membership = belonging_membership
        self.sync_vars = sync_vars
        self._modified_sync_vars: dict[str, SyncVar] = self.sync_vars.copy()

        # Add the default func only if on 'Server' Side
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            for name, sv in self.sync_vars.items():
                func = lambda old, new, name=name, sv=sv: self._on_sv_modified(name, sv)
                sv.on_changed.append(func)

        self.uid: str = uid
        self.is_alive = True
        self.type = self.__class__.__name__
        self.is_initialized = False


    def _on_sv_modified(self, name, sv):
        self._modified_sync_vars[name] = sv

    def get_sync_vars(self, get_value=False, get_only_if_changed=True, reset_changed_sv=True) -> dict[str, SyncVar | T]:
        """
        List all SyncVars initialized into the ReverbObject.
        :param get_value: Will get the value of the SyncVar if True else will return the object
        :param get_only_if_changed: Get the value only if changed
        :param reset_changed_sv: Reset the dict _modified_sync_vars to {} after getting.
        :return: A dict of all SyncVars or val of the SyncVar by their name.
        """
        ret = {}
        if get_only_if_changed:
            ret = {name: sv.value if get_value else sv for name, sv in self._modified_sync_vars.items()}
        else:
            ret = {name: sv.value if get_value else sv for name, sv in self.sync_vars.items()}

        if reset_changed_sv:
            self._modified_sync_vars = {}
        return ret

    def pack(self, only_sync_vars) -> dict[str, type | str | SyncVar]:
        """
        :param only_sync_vars: If True, return only a dict containing value of SyncVars, else return in addition the type and the belonging_membership
        :return: A dict of all necessary args that are linked between the server and the clients by their name
        """

        sync_vars: dict[str, dict[str, Any]] = {"sync_vars": self.get_sync_vars(get_value=True, get_only_if_changed=True)}
        ret = sync_vars
        if not only_sync_vars:
            ret = {"type": self.type, "belonging_membership": self.belonging_membership, "init_args": self.init_args} | sync_vars
        return ret

    def sync(self, sync_vars: dict[str, Any]):
        """
        - Call on the 'CLIENT' side to sync new ro data
        :param sync_vars: Dict of the name of the attribute and his value. The attribute needs to be a SyncVar.
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            for name, val in sync_vars.items():
                if hasattr(self, name):
                    attr: SyncVar | Any = self.__getattribute__(name)
                    if isinstance(attr, SyncVar):
                        attr._value = val
                    else:
                        raise TypeError(f"The attribute {name=} in {self} is not a SyncVar!")
                else:
                    raise AttributeError(f"The attribute {name=} is not found in {self}")
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

    def __repr__(self):
        return f"ReverbObject(type={self.type}, uid={self.uid}, bm={self.belonging_membership}) of {len(self.sync_vars)} SyncVars"

    def __del__(self):
        if VERBOSE == 2:
            ReverbObject.print_object(f"Destroying the object {self}")


class ReverbManager:
    """
    - This class is static!
    - It links ReverbObject to the reference of the ReverbObject!
    """
    REVERB_SIDE: ReverbSide = None
    REVERB_CONNECTION: Client | Server = None  # Client, or Server
    REVERB_OBJECTS: dict[str, ReverbObject | str] = {}
    REVERB_OBJECT_REGISTRY = {"ReverbObject": ReverbObject}  # Register all type
    ADMIN_KEY = random.randint(1000, 10000)
    ADMINS = []

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
    def get_reverb_objects_by_belonging_membership(belonging_membership: int) -> list[ReverbObject]:
        """
        :return: List of all ROs that belong to the client with the given membership
        """
        ro_lst = []
        for ro in ReverbManager.REVERB_OBJECTS.values():
            ro_lst.append(ro) if ro.belonging_membership == belonging_membership else None

        return ro_lst

    @staticmethod
    def ros_to_uids(ros: list[ReverbObject]) -> list[str]:
        """
        :return: List of all uids of the given ros
        """
        return [ro.uid for ro in ros]


    @staticmethod
    @server_event_registry.on_event("stop_server_admin")
    def on_stop_server_admin(clt: socket.socket):
        """
        - Call on the 'SEVER' side
        - Shutdown the server!
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            if clt in ReverbManager.ADMINS:
                ReverbManager.print_manager("An admin stop the server!")
                ReverbManager.REVERB_CONNECTION.stop_server()
                save_logs(PATH_LOG)
                os._exit(0)
            else:
                ReverbManager.print_manager("A user tried to stop the server without admin rights!")
        else:
            raise ReverbWrongSideError(ReverbSide.SERVER)

    @staticmethod
    def stop_server_admin():
        """
        - Call on the 'CLIENT' side
        - Send a package to stop the server. Only stop if the client is registered as an admin.
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            ReverbManager.REVERB_CONNECTION.send("stop_server_admin")
        else:
            raise ReverbWrongSideError(ReverbSide.CLIENT)

    @staticmethod
    def log_as_admin(key: int):
        """
        - Call on the 'CLIENT' side only
        - Try to grant admin right to the client
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            ReverbManager.REVERB_CONNECTION.send("grant_admin", key)
        else:
            raise ReverbWrongSideError(ReverbSide.CLIENT)

    @staticmethod
    @server_event_registry.on_event("grant_admin")
    def on_grant_admin(clt: socket.socket, key):
        """
        - Call on the 'SERVER' side
        - Grant admin right to a client
        :param key: Admin key sent by the client
        """
        response = "REFUSED"
        if key == ReverbManager.ADMIN_KEY and clt not in ReverbManager.ADMINS:
            ReverbManager.ADMINS.append(clt)
            ReverbManager.print_manager(f"The user '{clt.getpeername()[0]}' has been successfully granted to admin!")
            response = "GRANTED"
        else:
            ReverbManager.print_manager(
                f"WARNING: The user '{clt.getpeername()[0]}' tried to connect as admin but with wrong ADMIN_KEY or is already an admin!")
        ReverbManager.REVERB_CONNECTION.send_to(clt, "grant_admin_response", response)

    @staticmethod
    @client_event_registry.on_event("grant_admin_response")
    def on_grant_admin_response(clt: socket.socket, response):
        if response == "GRANTED":
            ReverbManager.print_manager(f"Successfully granted to admin!")
        elif response == "REFUSED":
            ReverbManager.print_manager(f"The server refused the admin right to you! (Wrong key or already admin)")

    @staticmethod
    def server_sync():
        """
        - Call on 'SERVER' side
        - Sync value from 'SERVER' to 'CLIENT' side
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            ros: dict[str, Any] = {}
            # Avoiding: "RuntimeError: dictionary changed size during iteration"
            for uid, ro in list(ReverbManager.REVERB_OBJECTS.items()):
                if ro != "DESTROYED": # If the RO is not destroyed
                    pack = ro.pack(only_sync_vars=ro.is_initialized) # Get bm and type if not initialized
                    if pack != {}:
                        ros[uid] = pack
                    if not ro.is_initialized:
                        ro.is_initialized = True
            if ros != {}:
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
                pack = ro.pack(only_sync_vars=False)
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
                f"New ReverbObject: {ro} add into '{ReverbManager.REVERB_SIDE.name}'")

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
    def on_server_sync(clt: socket.socket, ros: dict[str, int | str | dict[str, Any]], *args):
        """
        - Called on the 'Client' side
        - Called when the server syncs the state of ReverbObject with clients
        :param clt: The client socket
        :param ros: Dict[uids: Dict[name, val]]
        """
        for uid, ro_data in ros.items():
            try:  # try to get a reverb_object
                ro = ReverbManager.get_reverb_object(uid)
            except ReverbObjectNotFoundError:  # create a new one
                if VERBOSE == 2:
                    ReverbManager.print_manager(f"The ReverbObject: {uid=} is not found!\n"
                                                f"Try to create this object with: {ro_data=}")
                if ro_data.get("type") is not None:
                    t: str = ro_data["type"] # Type
                else:
                    raise ValueError(f"The ro_data doesnt contain \"type\". {ro_data=}")

                if ro_data.get("belonging_membership") is not None:
                    bm: int = ro_data["belonging_membership"]
                else:
                    raise ValueError(f"The ro_data doesnt contain \"belonging_membership\". {ro_data=}")

                if ro_data.get("init_args") is not None:
                    init_args: list[Any] = ro_data["init_args"]
                else:
                    raise ValueError(f"The ro_data doesnt contain \"init_args\". {ro_data=}")

                cls = ReverbManager.get_cls_by_type_name(t)  # Class


                try:
                    ro = cls(*init_args,  belonging_membership=bm)
                except TypeError:
                    raise TypeError(
                        f"Not enough param passed! You try to construct {cls} but those elements are passed {args}, {ro_data}")
                ro.uid = uid
                ReverbManager.add_new_reverb_object(ro)

            if ro_data.get("sync_vars") is not None:
                ro.sync(ro_data["sync_vars"])
            else:
                raise ValueError(f"The ro_data doesnt contain \"sync_vars\". {ro_data=}")

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
                 f"This may occur because the ro was removed and the syncing between the client and the server is not enough fast!"
                 f"\nOr just because the uid is not found!")
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


def handle_exit():
    """
    Trigger on exit
    """
    if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
        save_logs(PATH_LOG)


atexit.register(handle_exit)
