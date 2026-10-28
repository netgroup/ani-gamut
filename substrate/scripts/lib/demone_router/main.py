# main_router.py

import os
import time
from demone_reader import RouterDaemon
from handlers import handle_encap,handle_decap, handle_encap_rollback, handle_decap_rollback
from validator_handler import validator_handler
ROUTER_NAME = os.getenv("HOSTNAME")

max_retries = 30
attempt = 0

while attempt < max_retries:
    try:
        daemon = RouterDaemon(ROUTER_NAME)
        print("Connessione riuscita!")
        break

    except Exception as e:
        attempt += 1
        print(f"Tentativo {attempt}/{max_retries} fallito: {e}")
        time.sleep(1)

else:
    raise Exception("Impossibile connettersi")

# registra i tipi messaggio
daemon.register_handler("encap", handle_encap)
daemon.register_handler("decap", handle_decap)
daemon.register_handler("encap_rollback", handle_encap_rollback)
daemon.register_handler("decap_rollback", handle_decap_rollback)
daemon.register_handler("validate", validator_handler)


#daemon.register_handler("intermediate", handle_intermediate)

daemon.start()
