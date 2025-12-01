import os
import time

from pyreverb import reverb
from pyreverb.Exemple.client import start_client
from pyreverb.reverb import start_distant, ReverbSide

work_dir = os.path.dirname(os.path.abspath(__file__))
print(ReverbSide.SERVER.name)
choice = input("Is the host? (Y|n)>>>")
is_host = False
pid = ""
if choice == "Y" or choice == "":
    reverb.SERVER_PROCESS = start_distant(work_dir + "/server.py")
    print(f"SERVER PROCESS:{reverb.SERVER_PROCESS}")
    print("Starting client in 1 second...")
    time.sleep(1)
    is_host = True

start_client(is_host)
