# yanch
Yet another naive blockchain, in python.

Each blockchain node provides an HTTP server and a websocket server.
HTTP server is used to interact with the chain, websocket server is used
for the nodes to communicate with each other in P2P manner.

## P2P Message Flow
Currently there's only one p2p message type: ANNOUNCE message, with a list of block.
This message is used to broadcast oneself's latest blocks.

If one mines or receives some blocks, she MUST broadcast the last one.

On receiving blocks, the receiver can:
 - append received blocks to his chain and broadcast the last one if the received
   blocks are just beyond his latest one;
 - announce his latest block back to the sender if the received blocks are much later
   than his latest one;
 - do nothing if his latest block is equal to the received one.
 - announce his later blocks back to the sender if his latest one is later 
   than the received ones;


```
  Peer1                                      Peer2
    |                                          |
    |                                          |
    |  ANNOUNCE peer1's last block B1          | if B1.index == lastindex+1:
    | ---------------------------------------> |--+
    |                                          |  | append B1 to local chain
    |                                          |  | then broadcast B1
    |                                          |<-+
    |                                          |
    |                                          | elif B1.index > lastindex:
    |                                          |--+
    |                                          |  |
    |  ANNOUNCE peer2's last block B2          |  |
    | <--------------------------------------- |<-+
    |                                          |
    |                                          | elif B1.index == lastindex:
    |                                          |--+
    |                                          |  |  Do Nothing
    |                                          |<-+
    |                                          |
    |                                          | elif B1.index < lastindex:
    |                                          |--+
    |  ANNOUNCE peer2's blocks[B1.index+1:]    |  |
    | <--------------------------------------- |<-+
    |                                          |
```

## How to Run
The easiest way to run a three-nodes blockchain network is via docker:

```
 git clone https://github.com/zenkj/yanch.git
 cd yanch
 sudo docker build -t yanch .
 sudo docker-compose up -d
```

then you can access one node via http://localhost:8080, and another node
via http://localhost:8000, in your favorite browser. Try create a new block
from one node and refresh to check it from another node.

If there's no docker environment, nodes can be started manually:

```
 git clone https://github.com/zenkj/yanch.git
 cd yanch
 pip install -r requirements.txt
 API_PORT=8080 P2P_PORT=4000 python yanch.py &
 API_PORT=8090 P2P_PORT=4001 PEERS=localhost:4000 python yanch.py &
 API_PORT=8000 P2P_PORT=4002 PEERS=localhost:4000 python yanch.py &
```

virtualenv is recommended, before starting the above nodes:

```
 virtualenv -p python3 yanchenv
 source yanchenv/bin/activate
```
