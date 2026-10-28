"""Datapizza-free, RabbitMQ-free broker double for testing srv6_core.

Implements the RabbitBroker contract that messagging.MessageSender depends on:
  - send(topic, message)
  - wait_messageIDs(expected_ids, timeout=60) -> bool
so `MessageSender(FakeBroker())` works unchanged. The real RabbitBroker is used against
the live Containerlab + RabbitMQ; this double lets the core be tested with no lab.
"""
import json


class FakeBroker:
    def __init__(self, ack_results=None):
        self.sent = []                                   # list of (topic, message)
        self.ack_results = list(ack_results) if ack_results is not None else []
        self.default_ack = True

    def send(self, topic, message):
        self.sent.append((topic, json.loads(json.dumps(message))))  # deep copy

    def wait_messageIDs(self, expected_ids, timeout=60):
        return self.ack_results.pop(0) if self.ack_results else self.default_ack
