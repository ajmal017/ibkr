from ib_insync import IB, util
import time
import asyncio

import json

with open('var.json', 'r') as fp:
    data = json.load(fp)

market = 'snp'

host = data['common']['host']
port = data[market]['port']
cid = 0

<<<<<<< HEAD
with IB().connect(host=host, port=port, clientId=cid) as ib:
    print(ib.isConnected())
=======
ib = IB().connect(host, snp, 2)
>>>>>>> ce5cdd107a7c53670869b51f16d9a84e34f58811

async def pnlcoro(ib):
    '''Gets the pnl object'''
    acct = ib.managedAccounts()[0]
    pnl = ib.reqPnL(acct)

    await ib.pnlEvent

    return pnl

pnl = ib.run(pnlcoro(ib))

accsum = ib.accountSummary(account=ib.managedAccounts()[0])
df_ac = util.df(accsum)
df = df_ac[df_ac.tag.isin(["NetLiquidation", "AvailableFunds"])]

print(df)

print("\n*******\n")

print(pnl)

print("\n*******\n")