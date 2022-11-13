from flask import Flask,jsonify
import requests
import json
from urllib.request import urlopen
from bs4 import BeautifulSoup
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

months_dict = {
  1: "Styczeń",
  2: "Luty",
  3: "Marzec",
  4: "Kwiecień",
  5: "Maj",
  6: "Czerwiec",
  7: "Lipiec",
  8: "Sierpień",
  9: "Wrzesień",
  10: "Październik",
  11: "Listopad",
  12: "Grudzień"
}
inflation_data = None

@app.route("/")
def home():
    return "<p>Use to get current or history of prices of edo bonds</p><p>/bond/edo(month)(year)/(day)/price or /bond/edo(month)(year)/(day)/history</p> <p>example: /bond/edo1030/11/price</p>"

@app.before_first_request
def before_first_request():
    uri = "https://stat.gov.pl/download/gfx/portalinformacyjny/pl/wykresy/1/inflacja.json"
    try:
        uResponse = requests.get(uri)
    except requests.ConnectionError:
       return "Connection Error"  
    Jresponse = uResponse.text
    global inflation_data
    inflation_data = json.loads(Jresponse)  

@app.route('/bond/<pid>/<day>/price', methods=['GET'])      
def post(pid, day):   
    url = f"https://www.obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/{pid}"

    try:
        page = urlopen(url)
    except:
        return jsonify({'error':  "Error opening the URL"}), 404

    soup = BeautifulSoup(page, 'html.parser')
    try:
        percentage = get_percentage(soup)
        marge = get_marge(soup)
        bond_date = get_bond_date(soup)
    except:
        return jsonify({'error':  "something went wrong with collectin innitial data"}), 404
    
    day = int(day) - 1
    bond_date = bond_date + relativedelta(days=day)
    diff = bond_date + relativedelta(years=1) - datetime.utcnow()
    i = 0
    if diff.days > 0:
        td = datetime.utcnow() - bond_date
        price = 100 + td.days*(percentage/365)
        return jsonify({'current_price': format(round(price, 2), '.2f')}), 200, {'Content-Type': 'application/json; charset=utf-8'}

    price = 100 + percentage
    while diff.days < 0:
        i += 1 
        inflation = get_inflation(bond_date, i)
        td = datetime.utcnow() - (bond_date + relativedelta(years=i))
        if td.days > 365:
            price = price + (inflation + marge)/100*price
        else:
            price = price + td.days*((inflation + marge)/365)/100*price
        diff = diff + relativedelta(years=1) + datetime.utcnow() - datetime.utcnow()
    return jsonify({'current_price': format(round(price, 2), '.2f')}), 200, {'Content-Type': 'application/json; charset=utf-8'}

@app.route('/bond/<pid>/<day>/history', methods=['GET'])      
def posthis(pid, day):   
    url = f"https://www.obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/{pid}"

    try:
        page = urlopen(url)
    except:
        return jsonify({'error':  "Error opening the URL"}), 404

    soup = BeautifulSoup(page, 'html.parser')
    try:
        percentage = get_percentage(soup)
        marge = get_marge(soup)
        bond_date = get_bond_date(soup)
    except:
        return jsonify({'error':  "something went wrong with collecting innitial data"}), 404
    
    day = int(day) - 1
    bond_date = bond_date + relativedelta(days=day)
    bond_list = []
    diff = bond_date + relativedelta(years=1) - datetime.utcnow()
    i = 0
    if diff.days > 0:
        td = datetime.utcnow() - bond_date
        while i < td.days:                  
            price = 100 + i*(percentage/365)
            op_date = bond_date + relativedelta(days = i)
            element = {
                "date" : op_date.strftime("%Y-%m-%d"),
                "price" : format(round(price, 2), '.2f')
            }
            bond_list.append(element)
            i += 1
        return jsonify(bond = pid, values = bond_list)

    while i <= 365:                  
        price = 100 + i*(percentage/365)
        op_date = bond_date + relativedelta(days = i)
        element = {
                "date" : op_date.strftime("%Y-%m-%d"),
                "price" : format(round(price, 2), '.2f')
            }
        bond_list.append(element)
        i += 1

    price = 100 + percentage
    i = 0
    diff = diff - relativedelta(years=1)
    while diff.days < 0:
        i += 1
        try: 
            inflation = get_inflation(bond_date, i)
        except:
            return jsonify({'error':  "something went wrong with calculating inflation"}), 404
        td = datetime.utcnow() - (bond_date + relativedelta(years=i))
        if td.days > 365:
            bond_list.extend(make_history_price(price, i, 1, inflation, marge, bond_date, td))
            price = price + (inflation + marge)/100*price
        else:
            bond_list.extend(make_history_price(price, i, 1, inflation, marge, bond_date, td))
            price = price + td.days*((inflation + marge)/365)/100*price
        diff = diff + relativedelta(days=365)
    return jsonify(bond = pid, values = bond_list)


def get_inflation(bond_date, i):
    date_inflation = bond_date - relativedelta(months=2) + relativedelta(years=i)
    month_inflation = date_inflation.month
    year_inflation = date_inflation.year

    return float(inflation_data["data"][months_dict.get(month_inflation)][str(year_inflation)])

def get_percentage(soup):
    tag = soup.figcaption
    span = tag.find("span")
    temp = span.getText()
    percentage = temp.strip()
    percentage = percentage.replace(",", "." )
    percentage = percentage.replace("%", "" )
    return (float(percentage))

def get_marge(soup):
    div = soup.find("div", {"class": "product-details"})
    marge = (div.getText()).split("marża")[1].split()[0]
    marge = marge.replace(",", "." )
    marge = marge.replace("%", "" )
    return (float(marge))

def get_bond_date(soup):
    div = soup.find("div", {"class": "product-details"})
    temp_date = (div.getText()).split("Okres oprocentowania:")[1].split()[0]
    return (datetime.strptime(temp_date, '%d.%m.%Y'))

def make_history_price(price, i, j, inflation, marge, bond_date, td):
    tlist = []  
    while j < td.days  and j <= 365:               
        tmpprice = price + j*((inflation + marge)/365)/100*price
        op_date = bond_date + relativedelta(days = j) + relativedelta(years = i)
        j += 1
        element = {
                "date" : op_date.strftime("%Y-%m-%d"),
                "price" : format(round(tmpprice, 2), '.2f')
            }
        tlist.append(element)
    return tlist
