# get_connected.py
from ib_insync import *
def get_connected(market, trade_type):
    ''' get connected to ibkr
    Args: 
       (market) as string <'nse'> | <'snp'>
       (trade_type) as string <'live'> | <'paper'>
    Returns:
        (ib) object if successful
    '''
    
    ip = (market.upper(), trade_type.upper())
    
    #host dictionary
    hostdict = {('NSE', 'LIVE'): 3000,
                ('NSE', 'PAPER'): 3001,
                ('SNP', 'LIVE'): 1300,
                ('SNP', 'PAPER'): 1301}
    
    host = hostdict[ip]
    
    cid = 1 # initialize clientId
    max_cid = 5 # maximum clientId allowed. max possible is 32

    for i in range(cid, max_cid):
        try:
            ib = IB().connect('127.0.0.1', host, clientId=i)
            
        except Exception as e:
            print(e) # print the error
            continue # go to next
            
        break # successful try
        
    return ib

#_____________________________________

# get_dte.py
import datetime

def get_dte(dt):
    '''Gets days to expiry
    Arg: (dt) as day in string format 'yyyymmdd'
    Returns: days to expiry as int'''
    return (util.parseIBDatetime(dt) - 
            datetime.datetime.now().date()).days

#_____________________________________

# get_maxfallrisestd.py

from math import sqrt
import pandas as pd

def get_maxfallrisestd(ib, c, dte, tradingdays, durmult=3):
    '''gets the rolling max standard deviation
    Args:
        (ib) as connection object
        (c) as contract object
        (dte) as int for no of days for expiry
        (tradingdays) as int for trading days
        (durmult) no of samples to go backwards on
    Returns:
        hi52, lo52, fall, rise, std as tuple'''

    # determine the low52, hi52, fall, rise
    hist = ib.reqHistoricalData(contract=c, endDateTime='', 
                                        durationStr='365 D', barSizeSetting='1 day',  
                                                    whatToShow='Trades', useRTH=True)

    df = util.df(hist)
    df.insert(0, column='symbol', value=c.symbol)

    df_ohlc = df.set_index('date').sort_index(ascending=True)
    df = df_ohlc.assign(delta=df_ohlc.high.rolling(dte).max()-df_ohlc.low.rolling(dte).min(), pctchange=df_ohlc.high.pct_change(periods=dte))

    df1 = df.sort_index(ascending=False)
    max_fall = df1[df1.pctchange<=0].delta.max()
    max_rise = df1[df1.pctchange>0].delta.max()
    hi52 = df1.high.max()
    lo52 = df1.low.min()

    lhfr = (lo52, hi52, max_fall, max_rise)

    # for std, keep only durmult*dte
    df = df_ohlc.tail(durmult*dte)
    df_ohlc = df.sort_index(ascending = False)

    # get cumulative standard deviation
    df_stdev = pd.DataFrame(df_ohlc['close'].expanding(1).std(ddof=0))
    df_stdev.columns = ['stdev']

    # get cumulative volatility
    df_vol = pd.DataFrame(df_ohlc['close'].pct_change().expanding(1).std(ddof=0)*sqrt(tradingdays))
    df_vol.columns = ['volatility']

    df_ohlc1 = df_ohlc.join(df_vol)

    df_ohlc2 = df_ohlc1.join(df_stdev)

    ret = lhfr+(df_ohlc2.stdev.max(),)
    
    return ret

#_____________________________________

# catch.py
import numpy as np

def catch(func, handle=lambda e : e, *args, **kwargs):
    '''List comprehension error catcher
    Args: 
        (func) as the function
         (handle) as the lambda of function
         <*args | *kwargs> as arguments to the functions
    Outputs:
        output of the function | <np.nan> on error
    Usage:
        eggs = [1,3,0,3,2]
        [catch(lambda: 1/egg) for egg in eggs]'''
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return np.nan

#_____________________________________

# save_open_orders.py
def save_open_orders(ib, fspath='../data/snp/'):
    '''Saves the open orders, before deleting from the system
    Arg: 
        (ib) as connection object
        (fspath) to save the files
    Returns: None'''
    import pandas as pd
    import glob

#     fspath = '../data/snp/'
    fn = '_openorders'
    fe = '.pkl'

    filepresent = glob.glob(fspath+fn+fe)

    if filepresent:
        qn = input(f'File {[f for f in filepresent]} is available. Overwrite?: Y/N ')
        if qn.upper() != 'Y':
            return

    ib.reqAllOpenOrders()
    opTrades = ib.openTrades()

    if opTrades:
        dfopen = pd.DataFrame.from_dict({o.contract.conId: \
        (o.contract.symbol, \
        o.contract.lastTradeDateOrContractMonth, \
        o.contract.right, \
        o.order.action, \
        o.order.totalQuantity, \
        o.order.orderType, \
        o.order.lmtPrice, \
        o.contract, \
        o.order) \
        for o in opTrades}).T.reset_index()

        dfopen.columns = ['conId', 'symbol', 'expiration', 'right', 'action', 'qty', 'orderType', 'lmtPrice', 'contract', 'order']
        dfopen.to_pickle(fspath+fn+fe)
        return dfopen
    else:
        return None

#_____________________________________

# upd_opt.py
blk = 50
def upd_opt(ib, dfopts):
    '''Updates the option prices and roms
    (ib) as connection object
    (dfopts) as DataFrame with option contracts and optPrice in it'''
    
    # Extract the contracts
    contracts = [Contract(conId=c) for c in list(dfopts.optId)]
    
    # Qualify the contracts in blocks
    cblks = [contracts[i: i+blk] for i in range(0, len(contracts), blk)]
    qc = [c for q in [ib.qualifyContracts(*c) for c in cblks] for c in q]

    # Get the tickers of the contracts in blocks
    tb = [qc[i: i+blk] for i in range(0, len(qc), blk)]
    tickers = [t for q in [ib.reqTickers(*t) for t in tb] for t in q]

    # Generate the option price dictionary
    optPrices = {t.contract.conId: t.marketPrice() for t in tickers} # {symbol: optPrice}

    # Update the option prices and rom
    df = dfopts.set_index('optId')
    df.optPrice.update(pd.Series(optPrices))
    df = df.assign(rom=df.optPrice*df.lotsize/df.optMargin*252/df.dte).sort_values('rom', ascending=False)
    
    return df

#_____________________________________

# grp_opts.py
def grp_opts(df):
    '''Groups options and sorts strikes by puts and calls
    Arg: 
       df as dataframe. Requires 'symbol', 'strike' and 'dte' fields in the df
    Returns: sorted dataframe'''
    
    gb = df.groupby('right')

    if 'C' in [k for k in gb.indices]:
        df_calls = gb.get_group('C').reset_index(drop=True).sort_values(['symbol', 'dte', 'strike'], ascending=[True, False, True])
    else:
        df_calls =  pd.DataFrame([])

    if 'P' in [k for k in gb.indices]:
        df_puts = gb.get_group('P').reset_index(drop=True).sort_values(['symbol', 'dte', 'strike'], ascending=[True, False, False])
    else:
        df_puts =  pd.DataFrame([])

    df = pd.concat([df_puts, df_calls]).reset_index(drop=True)
    
    return df

#_____________________________________

# get_prec.py
# get precision, based on the base
from math import floor, log10

def get_prec(v, base):
    '''gives the precision value
    args:
       (v) as value needing precision in float
       (base) as the base value e.g. 0.05'''
    
    return round(round((v)/ base) * base, -int(floor(log10(base))))

#_____________________________________

# assign_var.py
import json
def assign_var(market):
    '''Assign variables using exec
    Arg: (market) as string <'nse'>|<'snp' 
    Returns: VarList as a list of strings containing assignments
             These will be executed upon using exec()'''

    with open('variables.json', 'r') as fp:
        varDict = json.load(fp)
    
    varList = [str(k+"='"+str(v)+"'")  if type(v) is str
               else (str(k+'='+ str(v))) if type(v) is list
               else str(k+'='+str(v)) for k, v in varDict[market].items()]
    return varList

#_____________________________________

# hvstPricePct.py
def hvstPricePct(dte):
    '''Gets expected price percentage from DTE for harvesting trades.
    Assumes max DTE to be 30 days.
    Arg: (dte) days to expiry as an int 
    Returns: expected harvest price percentage (xpp) as float
    Ref: http://interactiveds.com.au/software/Linest-poly.xls ... for getting curve function
    '''
#     if dte is to be extracted from contract.lastTradeDateOrContractMonth
#     dte = (util.parseIBDatetime(expiry) - datetime.datetime.now().date()).days
    
    if dte > 30:
        dte = 30  # Forces the max DTE to be 30 days
    
    xpp = (103.6008 - 3.63457*dte + 0.03454677*dte*dte)/100
    
    return xpp

#_____________________________________

# trade_blocks.py
def trade_blocks(ib, df, exchange):
    '''Makes SELL contract blocks for trades
    Args:
       (ib) as connection object
       (df) as the target df for setting up the trades
       (exchange) as the market <'NSE'|'SMART'>
    Returns:
       (coblks) as contract blocks'''
    
    if exchange == 'NSE':
        sell_orders = [LimitOrder(action='SELL', totalQuantity=q*l, lmtPrice=expPrice) for q, l, expPrice in zip(df.qty, df.lot, df.expPrice)]
    elif exchange == 'SMART':
        sell_orders = [LimitOrder(action='SELL', totalQuantity=q, lmtPrice=expPrice) for q, expPrice in zip(df.qty, df.expPrice)]
    # get the contracts
    cs=[Contract(conId=c) for c in df.optId]

    blks = [cs[i: i+blk] for i in range(0, len(cs), blk)]
    cblks = [ib.qualifyContracts(*s) for s in blks]
    qc = [z for x in cblks for z in x]

    co = list(zip(qc, sell_orders))
    coblks = [co[i: i+blk] for i in range(0, len(co), blk)]
    
    return coblks

#_____________________________________

# doTrades.py
def doTrades(ib, coblks):
    '''Places trades in blocks
    Arg: 
        (ib) as connection object
        (coblks) as (contract, order) blocks'''
    trades = []
    for coblk in coblks:
        for co in coblk:
            trades.append(ib.placeOrder(co[0], co[1]))
        ib.sleep(1)
        
    return trades

#_____________________________________

# riskyprice.py
def riskyprice(dft, prec):
    '''adjusts expPrice to accomodate fall-rise risk
    Args:
        (dft) as the options dataframe
        (prec) precision needed as int
    Returns:
        (riskyprice) as dictionary'''
    pmask = (dft.right == 'P') & (dft.undPrice-dft.strike-dft.expPrice < dft.Fall)
    df_prisky = pd.merge(dft[pmask][['symbol', 'optId', 'strike', 'right', 'dte', 'undPrice', 'optPrice', 'expPrice', 'Fall', 'Rise', 'expRom', 'qty']], 
             pd.DataFrame((dft[pmask].undPrice-dft[pmask].strike-dft[pmask].expPrice)), on=dft[pmask].index).drop('key_0', 1)

    cmask = (dft.right == 'C') & (dft.strike-dft.undPrice-dft.expPrice < dft.Rise)
    df_crisky = pd.merge(dft[cmask][['symbol', 'optId', 'strike', 'right', 'dte', 'undPrice', 'optPrice', 'expPrice', 'Fall', 'Rise', 'expRom', 'qty']], 
             pd.DataFrame((dft[cmask].strike-dft[cmask].undPrice-dft[cmask].expPrice)), on=dft[cmask].index).drop('key_0', 1)

    df_risky = pd.concat([df_prisky, df_crisky]).reset_index(drop=True)

    df_risky = df_risky.rename(columns={0: 'FallRise'})

    df_risky = df_risky.assign(FRpct=abs(np.where(df_risky.right == 'P', (df_risky.FallRise - df_risky.Fall)/df_risky.FallRise, (df_risky.FallRise - df_risky.Rise)/df_risky.FallRise)))

    df_risky = df_risky.sort_values('FRpct', ascending=False)

    df_risky = df_risky.assign(expPrice = get_prec(df_risky.FRpct*df_risky.expPrice, prec))

    return df_risky.set_index('optId')['expPrice'].to_dict()

#_____________________________________

