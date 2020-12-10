import discord
from discord.ext import tasks, commands
import time

import datetime
import asyncio
import calendar
import logging
from os import environ
from datetime import date, timedelta
from decimal import Decimal

from tastyworks.models import option_chain, underlying
from tastyworks.models.option import Option, OptionType
from tastyworks.models.order import (Order, OrderDetails, OrderPriceEffect,
                                     OrderType)
from tastyworks.models.session import TastyAPISession
from tastyworks.models.trading_account import TradingAccount
from tastyworks.models.underlying import UnderlyingType
from tastyworks.streamer import DataStreamer
from tastyworks.tastyworks_api import tasty_session


TOKEN_AUTH = "" # Retrieved from browser local storage on discord app (desktop)

client = discord.Client()

account = TastyAPISession(username="", password="")

recent_orders = []

scraped_channel = "765998792532033561" #day-trade-alerts
kindredd_channel = ""
#day-trade-alerts: 765998792532033561
#code cafe: 784119796400521216

max_contract_size = 4

def parse_alert(alert):
    #return a dictionary that parses alerts in the format of:
    #STC HALF/REST PTON 12/4 116C @ 1.92
    #BTO PTON 12/4 116C @ 1.92
    alert_dict = {
        "Entry": 0, #1 for bto 0 for stc
        "Ticker": "XXX", #Ticker symbol
        "Expire": "", #python datetime.datetime.date() object
        "Strike_P": 0, #strike price
        "P/C": "", #put or call
        "Contract_P": 0 #contract price (if using limit)

    }

    if ("@everyone" in alert):
        alert = alert.replace("@everyone", "")

    if ("@" in alert):
        alert = alert.replace("@", "")

    alert = alert.upper() #all caps


    alert_list = alert.split() #turn into list

    if(alert_list[0] == "STC" or alert_list[0] == "BTO"): #found a trade alert

        #alert found!

        if(alert_list[0] == "BTO"):
            alert_dict["Entry"] = 1
        else: #stc
            alert_dict["Entry"] = 0
            if("HALF" in alert_list[1] or "REST" in alert_list[1]): #these are irrelvant to us, (until we use more than 1 contract per alert)
                del alert_list[1]


        alert_dict["Ticker"] = alert_list[1]

        #handle expiration
        alert_date = alert_list[2].split("/")
        expireM = int(alert_date[0])
        expireD = int(alert_date[1])

        try: #see if there is a year
            expireY = alert_date[2] #would be in the format of two digits
            expireY = expireY + 2000 #this will stop working in 2100 AD
            true_expire = datetime.datetime(expireY, expireM, expireD)
            alert_dict["Expire"] = true_expire.date()
        except: #no year attached, do some checking to see what expiration year was most likely used
            current_date = datetime.datetime.now().date()
            current_year = datetime.datetime.now().year
            potential_expire =  datetime.datetime(current_year, expireM, expireD).date()


            if(current_date > potential_expire): # if this is true, the expiry is next year
                current_year = current_year + 1
            true_expire = datetime.datetime(current_year, expireM, expireD)
            alert_dict["Expire"] = true_expire.date()

        #expiration handled

        #handle strike p and if p/c
        alert_strike = alert_list[3]
        alert_dict["P/C"] = alert_strike[-1] #last char
        alert_dict["Strike_P"] = float(alert_strike[0:-1])

        #handle contract price
        if(alert_list[4] == "@"):
            del alert_list[4]

        alert_dict["Contract_P"] = float(alert_list[4])

        return [1, alert_dict]
    else:
        return [-1, alert_dict]

async def getAccountInfo(session):
    accounts = await TradingAccount.get_remote_accounts(session)
    acct = accounts[0]
    print("Tastyworks connected!")
    print("Account Number: " + str(acct.account_number))
    print("Current Positions: ")
    positions = await TradingAccount.get_positions(session=session, account=acct)
    for i in range(len(positions)): #iterate through positions object
        print(str(positions[i].quantity) + "x", end="")
        tick = " "+positions[i].underlying_symbol
        print(tick, end="")
        if(str(positions[i].quantity_direction) == "QuantityDirection.LONG"):
            print(" Calls")
        else:
            print(" Puts")
async def verify_position(option_dict):
    accounts = await TradingAccount.get_remote_accounts(account)
    acct = accounts[0]
    positions = await TradingAccount.get_positions(session=account, account=acct)
    for i in range(len(positions)):  # iterate through positions object
        callp = positions[i].quantity_direction
        tick = positions[i].underlying_symbol
        if(str(callp) == "QuantityDirection.LONG" ):
            callp = "C"
        else:
            callp = "P"
        if(callp == option_dict["P/C"]):
            if(tick == option_dict["Ticker"]):
                return 1

    return 0

async def send_order(session, option_dict):
    global recent_orders
    accounts = await TradingAccount.get_remote_accounts(session)
    acct = accounts[0]
    if(option_dict["Entry"] == 1):
        user_price_effect = OrderPriceEffect.DEBIT
    elif(option_dict["Entry"] == 0):
        user_price_effect = OrderPriceEffect.CREDIT

    details = OrderDetails(
        type=OrderType.LIMIT,
        price=Decimal(option_dict["Contract_P"]),
        price_effect=user_price_effect)
    new_order = Order(details)

    if(option_dict["P/C"] == "C"):
        optionUsed = OptionType.CALL
    elif(option_dict["P/C"] == "P"):
        optionUsed = OptionType.PUT
    opt = Option(
        ticker=option_dict["Ticker"],
        quantity=1,
        expiry=option_dict["Expire"],
        strike=Decimal(option_dict["Strike_P"]),
        option_type=optionUsed,
        underlying_type=UnderlyingType.EQUITY
    )
    new_order.add_leg(opt)

    res = await acct.execute_order(new_order, session, dry_run=False)
    return res

@client.event
async def on_ready():
    background_cog.start()
    await getAccountInfo(account)
    print("Bot Connected!")
@client.event
async def on_message(message):
    if(str(message.channel.id) == scraped_channel):
        alert_dict = parse_alert(message.content)
        #return codes:
        #-1 = Not an alert
        #1 = Success parsing alert

        print(alert_dict)
        #execute an order
        #make sure if its stc, the position exists
        pos = 1
        if(alert_dict[1]["Entry"] == 0):
            pos = await verify_position(alert_dict[1])
        if((alert_dict[1]["Contract_P"] > max_contract_size) and alert_dict[1]["Entry"] == 1): #dont use entire account on one trade (small accounts)
            pos = 0
        if(alert_dict[0] == 1 and pos == 1): #successfully found and parsed an alert: send an order
            print("Sending an Order!")
            resp = await send_order(account, alert_dict[1])
            print(resp)

@tasks.loop(seconds=1)
async def background_cog(): #basically cancel outstanding orders, or change stc limit orders to market if they dont fill
    removeable_ids = []
    global recent_orders
    max_holding_time = 30
    accounts = await TradingAccount.get_remote_accounts(account)
    acct = accounts[0]
    orders = await Order.get_live_orders(session=account, account=acct)
    for i in range(len(orders)):
        orderid = (orders[i].details).order_id
        if any(orderid in sublist for sublist in recent_orders):
            pass
        else:
            recent_orders.append([orderid, time.time()])

    for i in range(len(recent_orders)):
        id = recent_orders[i][0]
        id_time = recent_orders[i][1]
        if(time.time()-id_time > max_holding_time):
            removeable_ids.append(id)
            currentOrder = await Order.get_order(session=account, account=acct, order_id=id)
            if(currentOrder.details.price_effect == OrderPriceEffect.CREDIT and currentOrder.details.type == OrderType.LIMIT): #a stc order, MUST be filled so set up a market order
                old_order = currentOrder
                old_order.details.type = OrderType.MARKET
                details = OrderDetails(
                    type=OrderType.MARKET,
                    price_effect=OrderPriceEffect.CREDIT)
                new_order = Order(details)
                opt = Option(
                    ticker=old_order.details.legs[0].ticker,
                    quantity=1,
                    expiry=old_order.details.legs[0].expiry,
                    strike=old_order.details.legs[0].strike,
                    option_type=old_order.details.legs[0].option_type,
                    underlying_type=UnderlyingType.EQUITY
                )
                new_order.add_leg(opt)
                try:
                    await Order.cancel_order(session=account, account=acct, order_id=id)
                except Exception:
                    pass
                res = await acct.execute_order(new_order, session=account, dry_run=False)
                del recent_orders[i]
            elif(currentOrder.details.price_effect == OrderPriceEffect.CREDIT and currentOrder.details.type == OrderType.MARKET): #dont cancel stc market orders
                pass
            else:
                try:
                    await Order.cancel_order(session=account, account=acct, order_id=id)
                except Exception:
                    print("User cancelled.")
    for i in range(len(removeable_ids)):
        for j in range(len(recent_orders)):
            if(recent_orders[j][0] == removeable_ids[i]):
                del recent_orders[j]
            j = j - 1
client.run(TOKEN_AUTH, bot=False)
