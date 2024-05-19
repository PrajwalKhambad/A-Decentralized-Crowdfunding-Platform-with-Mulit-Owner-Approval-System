from web3 import Web3
import json

w3 = Web3(Web3.HTTPProvider('https://sepolia.infura.io/v3/7bd05cddb05345078c0ac02ee7804d9c')) 

with open('abi.json') as f:
    abi = json.load(f)
contract_address = '0x3643b7a9F6338115159a4D3a2cc678C99aD657aa'

contract = w3.eth.contract(address=contract_address, abi=abi)
