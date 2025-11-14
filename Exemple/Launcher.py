import time

from PyReverb.reverb import start_distant, ReverbSide
VENV_ACTIVATE_PATH = "../../.venv/bin/activate"
print(ReverbSide.SERVER.name)
choice = input("Is the host? (Y|n)>>>")
is_host = False
if choice == "Y" or choice == "":
    start_distant("./Game.py", ReverbSide.SERVER.name, VENV_ACTIVATE_PATH)
    print("Starting client in 1 second...")
    time.sleep(1)
    is_host = True

start_distant("./Game.py", ReverbSide.CLIENT.name, VENV_ACTIVATE_PATH, is_host)
time.sleep(0.5)