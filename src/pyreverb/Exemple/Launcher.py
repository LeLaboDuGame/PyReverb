import os
import time

from pyreverb.reverb import start_distant, ReverbSide

work_dir = os.path.dirname(os.path.abspath(__file__))
print(ReverbSide.SERVER.name)
choice = input("Is the host? (Y|n)>>>")
is_host = False
pid = ""
if choice == "Y" or choice == "":
    pid = start_distant(work_dir + "/Game.py", ReverbSide.SERVER.name).pid
    print("Starting client in 1 second...")
    time.sleep(1)
    is_host = True

start_distant(work_dir + "/Game.py", ReverbSide.CLIENT.name, is_host, str(pid))

