import os
import time

from pyreverb import reverb
from pyreverb.Exemple.client import start_client
from pyreverb.reverb import start_distant, ReverbSide

PORT = 26010
ADMIN_KEY = 1001

if __name__ == "__main__":
    work_dir = os.path.dirname(os.path.abspath(__file__))
    print(ReverbSide.SERVER.name)
    choice = input("Is the host? (Y|n)>>>")
    is_host = False
    pid = ""
    if choice == "Y" or choice == "":
        reverb.SERVER_PROCESS = start_distant(work_dir + "/server.py", str(PORT), str(ADMIN_KEY))
        print(f"SERVER PROCESS:{reverb.SERVER_PROCESS}")
        print("Starting client in 1 second...")
        time.sleep(1)
        is_host = True

    start_client(is_host, PORT, ADMIN_KEY)
