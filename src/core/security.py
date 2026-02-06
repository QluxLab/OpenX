import os
def newkey(n):
    return os.urandom(n).hex()

def new_sk():
    return f"sk-{newkey(32)}"

def new_rk():
    return f"rk-{newkey(48)}"