import time

from reverb import start_distant, ReverbSide
print(ReverbSide.SERVER.name)
choice = input("Is the host? (Y|n)>>>")
is_host = False
if choice == "Y" or choice == "":
    start_distant("Game.py", ReverbSide.SERVER.name)
    print("Starting client in 1 second...")
    time.sleep(1)
    is_host = True

start_distant("Game.py", ReverbSide.CLIENT.name, is_host)
