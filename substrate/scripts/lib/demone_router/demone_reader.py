# router_daemon.py

import json
import pika
import os
import time


class RouterDaemon:

    def __init__(self, router_name, rabbit_host="rabbit"):
        self.router = router_name
        self.rabbit_host = rabbit_host
        # registry funzioni per tipo messaggio
        self.handlers = {}
        self.response_queue =f"router.master.response"
        self.queue = f"router.{self.router}.commands"

        num = int(''.join(filter(str.isdigit,self.router)))
        self.sid = f"5f00:0:{num:x}::/48"
        self._connect()

    def _connect(self):
        """Connessione a RabbitMQ"""
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.rabbit_host)
        )
        self.channel = connection.channel()

        # exchange topic
        self.channel.exchange_declare(exchange="routers", exchange_type="topic")

        result = self.channel.queue_declare(queue=self.queue,durable=True)
        self.channel.queue_declare(queue=self.response_queue,durable=True)

        self.channel.queue_bind(
            exchange="routers",
            queue=self.queue,
            routing_key=self.queue
        )

        print(f"[{self.router}] Listening on topic: {self.queue}")

    def register_handler(self, message_type, func):
        """
        Registra una funzione handler per un tipo messaggio
        """
        self.handlers[message_type] = func

    def _process_message(self, ch, method, properties, body):
        try:
            message = json.loads(body)
            msg_id = message.get("msg_id")
            msg_type = message.get("type")
            print(f"[{self.router}] Received ",msg_id," message:", message)
            if msg_type not in self.handlers:
                print(f"[{self.router}] No handler for type: {msg_type}")
                return

            handler = self.handlers[msg_type]
            result=handler(message)
            print("msg_type: ",msg_type,"- risposta: ",result)
            response = {"msg_id": msg_id}| result
            self.channel.basic_publish(
                exchange="",
                routing_key=self.response_queue,
                body=json.dumps(response),
            )
            # === ACK RabbitMQ ===
            ch.basic_ack(delivery_tag=method.delivery_tag) 
        except Exception as e:
            print(f"[{self.router}] Error processing message:", e)
            response = {
                "msg_id": msg_id,
                "status": "error",
                "message":str(e)
            }
            self.channel.basic_publish(
                exchange="",
                routing_key=self.response_queue,
                body=json.dumps(response),
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
    def start(self):
        """Loop principale"""
        self.channel.basic_consume(
            queue=self.queue,
            on_message_callback=self._process_message,
            auto_ack=False
        )

        print(f"[{self.router}] Router daemon started sid: {self.sid}")

        self.channel.start_consuming()
