import requests
from bs4 import BeautifulSoup
import re
from random import uniform
from twilio.rest import TwilioRestClient
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from email.header import Header
import time
# set up twilio api keys (from twillio.com)
accountSID = '' # input here
authToken = '' # input here
twilioCli = TwilioRestClient(accountSID, authToken)
myTwilioNumber = '' # input here
myCellPhone = '' # input here
# where to send emails from?
email_address = '' # input here
email_password = '' # input here
# receiver email
recv_email = '' # input here

schedule = ""
schedule = str(input('enter time to run in HM format, for example 2:30pm would be 1430, or hit enter to run now'))
if len(schedule) > 0:
    print('bot scheduled to run at ' + schedule[:2] + ':' + schedule[2:])  
else:
    schedule = 0
# if no schedule then run once
def send_email():
    serv = smtplib.SMTP('smtp.gmail.com', 587)  # or other smtp
    serv.starttls()
    try:
        serv.login(email_address, email_password)
    except Exception as e:
        print('log in to email smtp server failed, probably wrong password: ', e)
        return
    msg = MIMEMultipart()
    msg['From'] = formataddr((str(Header('Scanner (2016)', 'utf-8')), email_address))   # creating email "from", "subject"
    msg['Subject'] = 'Scanner (2016) - Tickers below 52wk low ' + time.strftime("%x")
    msg.attach(MIMEText(email_text, 'plain'))
    print(email_text)
    serv.send_message(msg=msg, from_addr=email_address, to_addrs=recv_email)            # sending here


def dump_email(ticker, price, low, name):       # email body assembly
    global email_text
    email_text += 'Company name: ' + name + '\nTicker name: ' + ticker.upper() + '\nTicker price: ' + price + '\nDistance from 52w low: ' + low + '%\n\n'


def dump_sms(ticker):                           # sms body assembly
    global sms_text
    sms_text += ticker + ', '


def open_stack(ticker):
    global invested                                                 # is this stock already invested in?
    r1 = s1.get('http://finviz.com/quote.ashx?t=' + ticker.lower())  # request ticker page
    source = r1.text
    price = re.findall(r'Prev Close.+b>(.+?)</b', source)[0]        # find price with RegEx
    print('price:', price)
    bs1 = BeautifulSoup(r1.content)                                 # parse html content
    name = bs1.select('td[align="center"] a b')[-1].text            # scrape ticker name
    print(name)
    week_low = re.findall(r'52W Low.+>(.+?)%<', source)[0]          # find week_low with RegEx
    if not invested:
        if float(week_low) < 20:                                    # check if parameter corresponds to some investing strategy
            print('triggered')
            try:
                dump_email(ticker, price, week_low, name)
            except Exception as e:
                print('failed to send email', e)
            try:
                dump_sms(ticker.upper())
            except Exception as e:
                print('failed to send SMS', e)
    print('52w low:', week_low + '%')
    # write results to csv
    f = open('../screener_results(' + time.strftime("%m-%d-%Y").replace('/', '') + ').csv', 'a')
    f.write('"' + ticker + '","' + name + '","' + price + '","' + week_low + '","' + str(invested) + '"\n')
    f.close()
    invested = False   # reset flag for next result


while True:                                                             # constantly check time
    if int((time.strftime("%H%M"))) == int(schedule) or schedule == 0:  # check if it's time to run
        invested = False
        # write csv header
        f = open('../screener_results(' + time.strftime("%m-%d-%Y").replace('/', '') + ').csv', 'a')
        f.write('"Ticker","Company name","Price","Distance from 52w low","Already Invested?"\n')
        f.close()
        email_text, sms_text = '', ''
        s, s1 = requests.session(), requests.session()      # initialize sessions
        # spoof user-agent to be safe
        ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36"}  
        s.headers.update(ua)
        s1.headers.update(ua)
        # read csv with invested stocks and dump them into array
        fr = open('../investments.csv', 'r')
        f = fr.read().splitlines()
        fr.close()
        existing_stocks = []
        for existing_stock in f:
            existing_stocks.append(existing_stock)
        print(len(existing_stocks), 'existing stocks')
        # get screener
        r = s.get('http://finviz.com/screener.ashx?v=111&f=fa_debteq_u1,fa_eps5years_o20,fa_peg_u2,fa_pfcf_u60,fa_roa_pos,fa_roe_o15,fa_roi_o15&ft=4&o=-marketcap')
        while True:             # loop breaks when last page is reached (in line 123)
            bs = BeautifulSoup(r.content)          # parse html
            # get the stocks from the page
            page_stocks = bs.select('a.screener-link-primary')          
            for i in range(len(page_stocks)):
                print(page_stocks[i].text)
                if page_stocks[i].text in existing_stocks:
                    print('ticker already in list')
                    invested = True
                open_stack(page_stocks[i].text)
                time.sleep(uniform(2, 3))       # random timeout to act more human
            try:
                if bs.select('td a.tab-link')[-1].text == 'next':
                    r = s.get('http://finviz.com/' + bs.select('td a.tab-link')[-1]['href'])        # go to next page
                else:
                    break
            except Exception as e:
                print(e)
                pass
        send_email()
        print(sms_text)
        # retry twillio sms 3 times, then give up
        for _ in range(3):
            try:
                message = twilioCli.messages.create(body=str(sms_text), from_=myTwilioNumber, to=myCellPhone)
                print(message)
                break
            except Exception as e:
                print('sending SMS failed, retrying in 5 seconds', e)
                time.sleep(5)
                if _ == 4:
                    print('sending failed after 5 retries, probably twilio issue')
    if schedule == 0:       # if no schedule received - exit after one run
        break
    time.sleep(59)          # timeout for main loop that checks time of the day
