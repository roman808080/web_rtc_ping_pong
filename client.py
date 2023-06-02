#!/usr/bin/env python3
import socketio
import asyncio

sio = socketio.AsyncClient()


@sio.event
async def connect():
    print("I'm connected to the signaling server!")


@sio.event
async def ready():
    print('Received ready')
    await sio.emit('data', {'message': 'ping'})


@sio.event
async def data(data):
    print('Received: ', data)
    await sio.emit('data', {'message': 'ping'})


async def main():
    await sio.connect('http://localhost:4000')
    await sio.wait()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
