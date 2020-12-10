# Parabolic Options Python Trading Bot (tastyworks)

## Disclaimer

This is an unofficial, experimental bot that has the ability to wipe out accounts if not used correctly or understood. 

## Purpose

Place trades that are made from the Parabolic Options Discord server automatically. 

## Installation
Due to the nature of this there is a bit of "hacking" that needs to be done. 
### Python Setup
The brokerage side of the bot is all handled by a modified api so the only install is the discord.py library.
``pip install discord``
### Discord Setup
First we have to acquire your account id for discord to feed to the bot. 
1. Open up the **desktop** version of discord. 
2. Press ```Control + Shift + i``` this should open up the chrome dev tool. 
3. Next click the *Network* tab. 
4. Finally click through your various dms/channels until you a ```science``` file pop up. 
5. Click this file. 
6. Under the *Headers* tab, scroll down to *Request Headers*
7. Look for an *authorization* label followed by a long string of letters and numbers.
8. Copy this string of text, **not** including the label. 
9. Paste this into the ```TOKEN_AUTH``` variable in ```main.py```
10. Your bot should now be able to sign in as you. 

### TastyWorks Setup
Simply navigate to the ```account``` variable and type in your credentials as shown below: <br>
```account = TastyAPISession(username="YOUR_USER", password="YOUR_PASS")``` <br>
If you have multiple tastyworks accounts then just know that the bot will use your first account. 

## Custom Settings

To be done.

## Status
Currently able to buy and sell positions. 
If you are approved for selling uncovered options do not use! Current error.
## TODO

To be done. 
