
import pika
import json
import time
class RabbitBroker:
    def __init__(self, host="rabbit"):
        self.host = host
        self.queue_response="router.master.response"
        self.exchange_name = "routers" 
    
    def send(self, topic, message):
        """Manda messaggio a router specifico via EXCHANGE TOPIC"""
        # print(f"[BROKER] -> ({topic}): {message}")
        
        connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
        channel = connection.channel()
        
        channel.exchange_declare(exchange=self.exchange_name, exchange_type="topic")
        channel.basic_publish(
            exchange=self.exchange_name,
            routing_key=topic,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # persistent
        )
        connection.close()
        return
    
    def wait_messageIDs(self, expected_ids, timeout=60):
        connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
        channel = connection.channel()
        channel.queue_declare(queue=self.queue_response, durable=True)
        aggregator = MessageAggregator(expected_ids, timeout)
        
        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                aggregator.add_message(data)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                #print(f"[BROKER] callback error: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                
        channel.basic_consume(queue=self.queue_response, on_message_callback=callback)
        aggregator.start_time = time.time()
        while True:
            connection.process_data_events(time_limit=3)
            if aggregator.is_error_occurred():
                return False
            if aggregator.is_complete():
                connection.close()
                return True
            if time.time() - aggregator.start_time > timeout:
                connection.close()
                #print("timeout connection  ",time.time() - aggregator.start_time )
                return False

class MessageAggregator:
    def __init__(self, expected_ids, timeout):
        self.status = {rid: 0 for rid in expected_ids}
        self.timeout = timeout
        self.start_time = time.time()
        self.c=0
        self.num_min = len(expected_ids)
        self.err = 0

    def add_message(self, data):
        self.c += 1
        self.start_time = time.time()
        msg_id = data.get("msg_id")
        if data.get("status") =="error":
            self.err=1
        if msg_id in self.status:
            self.status[msg_id] = 1
        

    def is_error_occurred(self):
        return self.err == 1
    def is_complete(self):
        #if self.c<self.num_min:
        #    return False
        return all(v == 1 for v in self.status.values())
        
class MessageSender:
    def __init__(self, broker):
        self.broker = broker

    def send(self, router: str, message: dict):
        topic = f"router.{router}.commands"
        self.broker.send(topic, message)
        return message
    
    def wait_ack(self,expected_ids):
        s=self.broker.wait_messageIDs(expected_ids)
        return s
