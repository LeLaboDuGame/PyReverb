import socket
import uuid
from enum import Enum
from typing import Type, TypeVar

from reverb_kernel import *
from reverb_errors import *

T = TypeVar("T")

class ReverbSide(Enum):
    SERVER = 1
    CLIENT = 2

def check_if_json_serializable(*args):
    for arg in args:
        try:
            json.dumps(arg)
        except (TypeError, OverflowError):
            raise Exception(
                f"The arg: {arg} is not serializable ! It has to be serializable by JSON to be agree as a reverb_args.")

class ReverbObject:
    def __init__(self, *reverb_args, uid:str="Unknow", add_on_init:bool=True, belonging_membership:int=None):
        """
        - Base class of all object connected to the Network
        :param reverb_args: All the custom vars
        :param uid: The uid of the object, let it on None if you are not sure of what you're doing here
        :param add_on_init: When True the ReverbObject will be added into the ReverbManager automatically
        :param belonging_membership: This refers to the port of client. With this you can know if the RO is from a local instance or not. Let it on None if you're not sure what you're doing here
        """
        self.belonging_membership = belonging_membership
        self.reverb_args = reverb_args
        self.uid: str = uid
        self.type = self.__class__.__name__

        if add_on_init:
            ReverbManager.add_new_reverb_object(self, self.uid)

    def pack(self):
        """
        :return: A list of all needed args that are linked between the server and the clients
        """
        check_if_json_serializable(*self.reverb_args)
        return [self.type, self.belonging_membership, list(self.__dict__.values())[:len(self.reverb_args)]]

    def sync(self, *reverb_args):
        """
        - Call on the 'CLIENT' side to sync new ro data
        - Know that values into reverb_args will be applied to variable along the position into the init
        :param reverb_args: List of args
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            if len(self.reverb_args) != len(reverb_args):
                raise ValueError(f"Length of argument in the class are not the same than the server send: "
                                 f"expected {len(self.reverb_args)} got {len(reverb_args)}")
            else:
                if reverb_args != ():
                    for key, val in zip(self.__dict__, reverb_args):
                        setattr(self, key, val)
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

    def is_owner(self):
        """
        - Chek if the ReverbObject is membership of this client
        - Only call on 'CLIENT' side
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
        ReverbManager.REVERB_CONNECTION.send("calling_server_computing", self.uid, func.__name__, *args)

    def is_uid_init(self):
        """
        :return: if uid is init or not
        """
        return self.uid is not "Unknow"

    def on_init_from_client(self):
        """
        - Call on 'CLIENT' side
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
        - Call on 'CLIENT' side
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
        ReverbObject.print_object(f"Destroying the object {self.uid=}")

class ReverbManager:
    """
    - This class is static !
    - It links ReverbObject to the reference of the ReverbObject !
    """
    REVERB_SIDE: ReverbSide = ReverbSide.SERVER
    REVERB_CONNECTION = None  # Client, or Server
    REVERB_OBJECTS: dict[str, ReverbObject] = {}
    REVERB_OBJECT_REGISTRY = {"ReverbObject": ReverbObject}  # Register all type

    @staticmethod
    def print_manager(msg):
        """
        - Print a message with the ReverbManager style
        :param msg: The message
        """
        print(f"{Back.YELLOW + Fore.RED}[{Fore.RESET}REVERB_MANAGER{Fore.RED}]{Style.RESET_ALL} {msg}")

    @staticmethod
    def add_type_if_dont_exit(ro: type[ReverbObject]):
        try:
            ReverbManager.REVERB_OBJECT_REGISTRY[ro.__name__]
        except KeyError:
            ReverbManager.REVERB_OBJECT_REGISTRY[ro.__name__] = ro
            ReverbManager.print_manager(f"Adding type '{ro.__name__}' to the registry.")

    @staticmethod
    def server_sync():
        """
        - Call on 'SERVER' side
        - Sync value from 'SERVER' to 'CLIENT' side
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            ros = {}
            for uid, ro in ReverbManager.REVERB_OBJECTS.items():
                ros[uid] = ro.pack()

            ReverbManager.REVERB_CONNECTION.send_to_all("server_sync", ros)
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE)

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
    def get_all_ro_by_type(t:Type[T]) -> list[T]:
        """
        - Get all the ReverbObject by a type
        :param t: Type of ReverbObject
        :return: Return the list of all found same type into the ReverbManager
        """
        ros = []
        for uid, ro in ReverbManager.REVERB_OBJECTS.items():
            if isinstance(ro, t):
                ros.append(ro)
        return ros

    @staticmethod
    def add_new_reverb_object(ro: ReverbObject, uid: str = "Unknown"):
        """
        - Add a new ReverbObject to the ReverbManager
        :param ro: The ReverbObject
        :param uid: The uid, can be let by default if you are on SERVER side
        """
        if ro not in ReverbManager.REVERB_OBJECTS.values():  # Check if the
                if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:  # check RM side
                    if not ro.is_uid_init():  # Check if the RO is not init yet
                        # SERVER
                        uid = str(uuid.uuid4())
                        ReverbManager.REVERB_OBJECTS[uid] = ro
                        ro.uid = uid
                        ro.on_init_from_server()
                    else:
                        raise ReverbUIDAlreadyInitError(ro)
                else:
                    # CLIENT
                    if uid is not "Unknow":
                        ReverbManager.REVERB_OBJECTS[uid] = ro
                    else:
                        raise ReverbUIDNoneError(uid)
                    ro.on_init_from_client()
        else:
            raise ReverbObjectAlreadyExistError(ro)

        ReverbManager.print_manager(f"New ReverbObject: {ro} add into '{ReverbManager.REVERB_SIDE.name}' side with uid={uid}")

    @staticmethod
    def remove_reverb_object(uid:str):
        """
        - Call on 'SERVER' side only
        - Remove the ro from all clients
        :param uid: The uid of the RO
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.SERVER:
            try:
                ro: ReverbObject = ReverbManager.REVERB_OBJECTS[uid]
                ro.on_destroy_from_server()
                ro.__del__()
                ReverbManager.REVERB_OBJECTS.pop(uid)
            except KeyError:
                raise KeyError(f"The {uid=} is not found !")
            ReverbManager.REVERB_CONNECTION.send_to_all("remove_ro", uid)
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE)

    @staticmethod
    @client_event_registry.on_event("remove_ro")
    def on_server_remove_reverb_object(clt:socket.socket, uid, *args):
        """
        - Only call on 'CLIENT' side
        - Remove the object
        :param clt: The socket
        :param uid: The uid of the ReverbObject to delete
        """
        if ReverbManager.REVERB_SIDE == ReverbSide.CLIENT:
            try:
                ro:ReverbObject = ReverbManager.REVERB_OBJECTS[uid]
                ro.on_destroy_from_client()
                ro.__del__()
                ReverbManager.REVERB_OBJECTS.pop(uid)
            except KeyError:
                raise KeyError(f"The server send a packet to remove a ro but the ro with the {uid=} is not found!")
        else:
            raise ReverbWrongSideError(ReverbManager.REVERB_SIDE)


    @staticmethod
    @client_event_registry.on_event("server_sync")
    def on_server_sync(clt: socket.socket, ros: dict[str, list[list[object]]], *args):
        """
        - Called on the 'Client' side
        - Called when the server sync state of ReverbObject with clients
        :param clt: The client socket
        :param ros: Dict[uids:list[list(values)]]
        """
        for uid, ro_data in ros.items():
            ro:ReverbObject = None
            try:  # try to get a reverb_object
                ro = ReverbManager.get_reverb_object(uid)
            except ReverbObjectNotFoundError:  # create a new one
                t:str = ro_data[0]
                cls = ReverbManager.get_cls_by_type_name(t)
                ro = cls(*ro_data[:2], belonging_membership=ro_data[1], uid=uid)
            ro.sync(*ro_data[2:][0])

    @staticmethod
    @server_event_registry.on_event("calling_server_computing")
    def on_calling_server_computing(clt: socket.socket, uid: str, func_name: str, *args):
        """
        - Called on the 'Server' side
        - Called when a ReverbObject send data to be computes by the server (like movements, interactions, etc.)
        :param clt: The client socket
        :param uid: The uid of the ReverbObject
        :param func_name: The function name
        :param args: Params of the function
        """
        ro = ReverbManager.get_reverb_object(uid)
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