#!/usr/bin/env python3
import socketio
import asyncio

from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling

import json
import logging
import os
import sys

from aiortc.sdp import candidate_from_sdp, candidate_to_sdp

sio = socketio.AsyncClient()
pc = RTCPeerConnection()


@sio.event
async def connect():
    print("I'm connected to the signaling server!")


@sio.event
async def ready():
    print('Received ready from the signaling server')
    await sio.emit('data', {'type': 'ping'})

    print('Create RTCPeerConnection on the offer side')
    await set_offer_side_handlers()
    offer = await create_offer()

    await sio.emit('data', {'type': 'offer',
                            'offer': object_to_string(offer)})


@sio.event
async def data(data):
    print('Received from the signaling server: ', data)

    if 'type' in data and data['type'] == 'ping':
        await asyncio.sleep(1)
        await sio.emit('data', {'type': 'ping'})


########################################################
#### Channel's methods
def channel_log(channel, t, message):
    print("channel(%s) %s %s" % (channel.label, t, message))


def channel_send(channel, message):
    channel_log(channel, ">", message)
    channel.send(message)
########################################################


########################################################
### Methods for converting str to obj and vice versa
def object_from_string(message_str):
    message = json.loads(message_str)
    if message["type"] in ["answer", "offer"]:
        return RTCSessionDescription(**message)
    elif message["type"] == "candidate" and message["candidate"]:
        candidate = candidate_from_sdp(message["candidate"].split(":", 1)[1])
        candidate.sdpMid = message["id"]
        candidate.sdpMLineIndex = message["label"]
        return candidate
    elif message["type"] == "bye":
        return BYE


def object_to_string(obj):
    if isinstance(obj, RTCSessionDescription):
        message = {"sdp": obj.sdp, "type": obj.type}
    elif isinstance(obj, RTCIceCandidate):
        message = {
            "candidate": "candidate:" + candidate_to_sdp(obj),
            "id": obj.sdpMid,
            "label": obj.sdpMLineIndex,
            "type": "candidate",
        }
    else:
        assert obj is BYE
        message = {"type": "bye"}
    return json.dumps(message, sort_keys=True)
########################################################


async def consume_signaling(pc, signaling):
    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)

            if obj.type == "offer":
                # send answer
                await pc.setLocalDescription(await pc.createAnswer())
                await signaling.send(pc.localDescription)
        elif isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
        elif obj is BYE:
            print("Exiting")
            break


async def set_answer_side_handlers(pc, signaling):
    @pc.on("datachannel")
    def on_datachannel(channel):
        channel_log(channel, "-", "created by remote party")

        @channel.on("message")
        def on_message(message):
            channel_log(channel, "<", message)

            if isinstance(message, str) and message.startswith("ping"):
                # reply
                channel_send(channel, "pong" + message[4:])


async def set_offer_side_handlers():
    channel = pc.createDataChannel("chat")
    channel_log(channel, "-", "created by local party")

    async def send_pings():
        while True:
            channel_send(channel, "ping %d" % current_stamp())
            await asyncio.sleep(1)

    @channel.on("open")
    def on_open():
        asyncio.ensure_future(send_pings())

    @channel.on("message")
    def on_message(message):
        channel_log(channel, "<", message)

        if isinstance(message, str) and message.startswith("pong"):
            elapsed_ms = (current_stamp() - int(message[5:])) / 1000
            print(" RTT %.2f ms" % elapsed_ms)

async def create_offer():
    await pc.setLocalDescription(await pc.createOffer())
    return pc.localDescription

########################################################


async def main():
    await sio.connect('http://localhost:4000')
    await sio.wait()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
