#!/usr/bin/env python3
import socketio
import asyncio

from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling

import json
import logging
import os
import sys
import time

from aiortc.sdp import candidate_from_sdp, candidate_to_sdp

sio = socketio.AsyncClient()
pc = RTCPeerConnection()
is_ready = False


@sio.event
async def connect():
    print("I'm connected to the signaling server!")


@sio.event
async def ready():
    print('Received ready from the signaling server')
    print('Create RTCPeerConnection on the offer side')

    global is_ready
    is_ready = True

    await set_offer_side_handlers()
    offer = await create_offer()
    await send_data(data=offer)


@sio.event
async def data(data):
    print('Received from the signaling server: ', data)
    print('Type:', type(data))

    global is_ready
    if is_ready == False:
        await set_answer_side_handlers()
        is_ready = True

    await handle_signaling(data=data)

async def send_data(data):
    await sio.emit('data', object_to_string(data))


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


async def handle_signaling(data):
    obj = object_from_string(message_str=data)

    if isinstance(obj, RTCSessionDescription):
        await pc.setRemoteDescription(obj)

        if obj.type == "offer":
            # send answer
            await pc.setLocalDescription(await pc.createAnswer())
            await send_data(data=pc.localDescription)
    elif isinstance(obj, RTCIceCandidate):
        await pc.addIceCandidate(obj)
    elif obj is BYE:
        print("Exiting")


async def set_answer_side_handlers():
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


time_start = None


def current_stamp():
    global time_start

    if time_start is None:
        time_start = time.time()
        return 0
    else:
        return int((time.time() - time_start) * 1000000)


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
