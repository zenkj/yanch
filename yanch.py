import gevent
from gevent import monkey
monkey.patch_all()

import time
import json
from hashlib  import sha256
from operator import itemgetter, attrgetter
from flask    import Flask, request, render_template, redirect, url_for


# P2P消息流程
#   当前只有一种P2P消息类型：ANNOUNCE消息，消息内容是一个区块列表。
#   这个消息既可以用来广播自己的最新区块，也可以定向向某个节点请求最新区块，
#   还可以向请求新区块的节点应答新区块。
#   
#   如果一个节点的本地链发生变更，它必须将最新区块广播给自己的所有对端。
#   
#   On receiving blocks, the receiver can:
#    - append received blocks to his chain and broadcast the last one if the received
#      blocks are just beyond his latest one;
#    - announce his latest block back to the sender if the received blocks are much later
#      than his latest one;
#    - announce his later blocks back to the sender if his latest one is later 
#      than the received ones;
#    - do nothing if his latest block is equal to the received one.
#
#  Peer1                                      Peer2
#    |                                          |
#    |                                          |
#    |  ANNOUNCE peer1's last block B1          | if B1.index == lastindex+1:
#    | ---------------------------------------> |--+
#    |                                          |  | append B1 to local chain
#    |                                          |  | then broadcast B1
#    |                                          |<-+
#    |                                          |
#    |  ANNOUNCE peer1's last block B1          | if B1.index > lastindex:
#    | ---------------------------------------> |--+
#    |                                          |  |
#    |  ANNOUNCE peer2's last block B2          |  |
#    | <--------------------------------------- |<-+
#    |                                          |
#    |                                          | elif B1.index < lastindex:
#    |                                          |--+
#    |  ANNOUNCE peer2's blocks[B1.index+1:]    |  |
#    | <--------------------------------------- |<-+
#    |                                          |
#    |                                          | elif B1.index == lastindex:
#    |                                          |--+
#    |                                          |  |  Do Nothing
#    |                                          |<-+
#    |                                          |

class Block(object):
    def __init__(self, index, timestamp, lasthash, data):
        self.index = index;
        self.timestamp = timestamp;
        self.lasthash = lasthash;
        self.data = data;
        self.hash = self.make_hash()

    def make_hash(self):
        h = sha256()
        value = '{},{},{},{}'.format(self.index, self.timestamp,
                                     self.lasthash, self.data)
        h.update(bytes(value, 'utf-8'))
        return h.hexdigest()

    def json(self):
        return {'index': self.index,
                'timestamp': self.timestamp, 
                'lasthash': self.lasthash,
                'data': self.data,
                'hash': self.hash,}

class BlockChain(object):
    # 2018.1.13 09:13:04 CST the first block is always the same for BlockChain instances
    genesis = Block(0, 1515805964, '', 'yet another genesis naive block')

    def __init__(self):
        self.chain = [self.genesis]

    def add_block_by_data(self, data):
        last = self.chain[-1]
        block = Block(last.index+1, int(time.time()), last.hash, data)
        self.chain.append(block)

    def add_blocks(self, jsondata):
        for jsonblock in jsondata:
            block = Block(jsonblock['index'], jsonblock['timestamp'], 
                          jsonblock['lasthash'], jsonblock['data'])
            if block.hash != jsonblock['hash'] or \
               not self.is_valid_new_block(block):
                raise ValueError('Invalid block: {}'.format(jsonblock))
            self.chain.append(block)

    def is_valid_new_block(self, block):
        last = self.chain[-1]
        if block.index == last.index+1 and \
           block.lasthash == last.hash and \
           block.timestamp >= last.timestamp:
               return True
        return False

    def last_blocks(self, n=1):
        length = len(self.chain)
        if n <= 0 or n > length:
            n = length
        return self.chain[-n:]

    def handle_msg(self, msg, peer_ws):
        data = json.loads(msg.decode('utf-8'))
        tp = data['type']
        blocks = data['blocks']
        if tp != P2P_MSG_TYPE or type(blocks) != list or len(blocks) <= 0:
            return
        blocks.sort(key=itemgetter('index'))
        selfi = len(self.chain) - 1
        selfindex = self.chain[selfi].index
        msgi = len(blocks) - 1
        while msgi >= 0:
            if blocks[msgi]['index'] <= selfindex+1:
                break
            msgi -= 1

        msgindex = blocks[msgi]['index']
        if msgindex == selfindex+1:
            # 直接附加到本地链
            self.add_blocks(blocks[msgi:])
            # 然后将自己的最新块广播出去
            # 否则自己链接的对端可能就收不到最新块
            p2p_broadcast(self.chain[-1:])
        elif msgindex > selfindex:
            # 对方超出本地链太多，把本地最新块发过去
            # 对方收到后，会将超出本地部分发过来
            send_blocks(peer_ws, self.chain[-1:])
        elif msgindex == selfindex:
            # 本地链长度与对方相同，什么都不用做
            # bugfix: 刚开始没处理这种情况，导致
            #         两个节点之间出现死循环
            pass
        else:
            # 本地链更长，将超出部分发回给对方，让它更新
            while selfi >= 0:
                if self.chain[selfi].index <= msgindex+1:
                    break
                selfi -= 1
            send_blocks(peer_ws, self.chain[selfi:])

import os
API_PORT = int(os.getenv('API_PORT', 8080))
P2P_PORT = int(os.getenv('P2P_PORT', 5678))
PEERS = os.getenv('PEERS', '').strip()

P2P_MSG_TYPE = 'ANNOUNCE'

chain = BlockChain()
peers = []

apiapp = Flask(__name__)

@apiapp.route("/")
def index():
    blocks = chain.last_blocks(-1)
    blocks.sort(key=attrgetter('index'), reverse=True)
    return render_template('index.html', blocks=blocks)

@apiapp.route("/mineblock", methods=['POST'])
def api_mine_block():
    data = request.form['block-data']
    chain.add_block_by_data(data)
    p2p_broadcast(chain.last_blocks(1))
    return redirect(url_for('index'))

@apiapp.route("/blocks")
def api_blocks():
    blocks =  [block.json() for block in chain.last_blocks(-1)]
    return json.dumps(blocks)

@apiapp.route("/addpeers", methods=['POST'])
def api_add_peers():
    data = request.form['peers']
    add_peers(data)
    return redirect(url_for('index'))

import websocket
def receiver(ws):
    while True:
        msg = ws.recv()
        chain.handle_msg(msg, ws)

def send_blocks(ws, blocks):
    blocks = [block.json() for block in blocks]
    data = {'type': P2P_MSG_TYPE, 'blocks': blocks}
    msg = json.dumps(data).encode('utf-8')
    ws.send(msg)

def p2p_broadcast(blocks):
    for peer in peers:
        peer.send_blocks(blocks)

class Peer(object):
    def __init__(self, ws, **kwargs):
        client = False
        for key in kwargs:
            if key == 'client':
                client = kwargs[key]
                break
        self.ws = ws
        if client:
            self.receiver = gevent.spawn(receiver, ws)
            print(self.receiver)

    def send_blocks(self, blocks):
        try:
            send_blocks(self.ws, blocks)
        except:
            print('Peer: send failed')
            peers.remove(self)

def add_peers(peersdata):
    def connect(address):
        # 服务端还没启动好时, 每隔10秒重试1次，重试100分钟
        retry = 0
        while retry < 600:
            try:
                ws = websocket.create_connection('ws://{}'.format(address))
                peer = Peer(ws, client=True)
                # 连接后立刻发送自己的最新块到服务端
                peer.send_blocks(chain.last_blocks(1))
                peers.append(peer)
                break
            except:
                retry += 1
                print('connect to "{}" failed, retry {}...'.format(address, retry))
                gevent.sleep(10)

    for address in peersdata.split(','):
        addr = address.strip()
        if addr: gevent.spawn(connect, addr)

add_peers(PEERS)

from gevent.pywsgi import WSGIServer

apiserver = WSGIServer(('', API_PORT), apiapp)
apiserver.start()

from geventwebsocket import WebSocketServer, WebSocketApplication, Resource
from collections import OrderedDict

class P2PApplication(WebSocketApplication):
    def on_open(self):
        # 被连接时客户端会立刻把自己的最新块发过来，
        # 所以无需给对端发送自己的最新区块。
        peers.append(Peer(self.ws))

    def on_message(self, message):
        chain.handle_msg(message, self.ws)

    def on_close(self, reason):
        pass

resource = Resource(OrderedDict([('/', P2PApplication)]))
p2pserver = WebSocketServer(('', P2P_PORT), resource)
p2pserver.start()

while True:
    gevent.sleep(60)
