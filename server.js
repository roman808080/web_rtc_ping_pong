const express = require('express');
const app = express();
const server = require('http').Server(app);
const io = require('socket.io')(server);

app.get('/', (req, res) => {
  res.send('Hello World!');
});

io.on('connection', (socket) => {
  console.log('A user connected: ' + socket.id);

  socket.on('disconnect', () => {
    console.log('A user disconnected: ' + socket.id);
  });

  socket.on('signal', (data) => {
    socket.broadcast.emit('signal', data);
  });
});

server.listen(3000, () => {
  console.log('Server is running on http://localhost:3000');
});
