# yanaivechain
yet another naive blockchain in python, based on [naivechain](https://github.com/lhartikk/naivechain),
with several enhancement.

## P2P Message Flow
Currently there's only one p2p message type: ANNOUNCE message, with a list of block.
This message is used to broadcast oneself's current last blocks.

If one mines or receives some blocks, she MUST broadcast the last one.

On receiving blocks, the receiver can:
 - append received blocks to his chain and broadcast the last one if the received
   blocks are just beyond his latest one;
 - announce his latest block back to the sender if the received blocks are much later
   than his latest one;
 - announce his later blocks back to the sender if his latest one is later 
   than the received ones;
 - do nothing if his latest block is equal to the received one.


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
    |  ANNOUNCE peer1's last block B1          | if B1.index > lastindex:
    | ---------------------------------------> |--+
    |                                          |  |
    |  ANNOUNCE peer2's last block B2          |  |
    | <--------------------------------------- |<-+
    |                                          |
    |                                          | elif B1.index < lastindex:
    |                                          |--+
    |  ANNOUNCE peer2's blocks[B1.index+1:]    |  |
    | <--------------------------------------- |<-+
    |                                          |
    |                                          | elif B1.index == lastindex:
    |                                          |--+
    |                                          |  |  Do Nothing
    |                                          |<-+
    |                                          |
```

## Installation
Easiest way to run a three-nodes blockchain network is by docker:

```
 git clone https://github.com/zenkj/yanch.git
 cd yanch
 sudo docker build -t yanch .
 sudo docker-compose up -d
```

then you can access one node via http://localhost:8080, and another node
via http://localhost:8000, in your favorite browser. Try create a new block
on one node and refresh to check it on another node.
