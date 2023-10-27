#Find a fucking GPU 
#Author: ropeadope62
#Version: 0.1
#This is a web scraper that will scrape memory Express and Newegg.ca for a given search term and return a list of inventory as a table including 

import requests
from bs4 import BeautifulSoup
from time import time, sleep

def check_memexpress():
#This is the code that is scraping the website.
    scrape_time: int = int(input('How long should I search for stock? (in minutes)'))
    scrape_time = scrape_time * 60
    scrape_refresh: int = int(input('How often should I refresh the query? (in minutes'))
    scrape_refresh = scrape_refresh * 60
    search_term = input('What item would you like to search? ')
    while scrape_time > 0:
        scrape_time -= 1
        names = []
        prices = []
        page = requests.get("https://www.memoryexpress.com/Search/Products?Search={search_term}".format(search_term=search_term))
        soup = BeautifulSoup(page.content, 'html.parser')
        items = soup.find_all('div', {'class':'item-container'})
        
        #Finding the name and price of the item.
        for item in items:
            names.append(item.find('a', {'class': "item-title"}).text.strip('\n').strip(' ').strip('\n'))
            for price in item.find_all('li', {'class': 'price-current'}):
                prices.append(''.join([price.strong.text.strip(), price.sup.text.strip()]))

        #Zipping the prices and names together.
        items_prices = zip(prices, names)

        #Printing the item number, price, and name of the item.
        global cc_stock_table 
        cc_stock_table = [] 
        for n, (price, item) in enumerate(items_prices):
            print('Item#{n}: {p} : {i}'.format(n=n+1, p=price, i=item))
        sleep(scrape_refresh)


def check_newegg():
#This is the code that is scraping the website.
    scrape_time: int = int(input('How long should I search for stock? (in minutes)'))
    scrape_time = scrape_time * 60
    scrape_refresh: int = int(input('How often should I refresh the query? (in minutes'))
    scrape_refresh = scrape_refresh * 60
    search_term = input('What item would you like to search? ')
    while scrape_time > 0:
        scrape_time -= 1
        names = []
        prices = []
        page = requests.get("https://www.newegg.ca/p/pl?d=={search_term}".format(search_term=search_term))
        soup = BeautifulSoup(page.content, 'html.parser')
        items = soup.find_all('div', {'class':'item-container'})
        
        #Finding the name and price of the item.
        for item in items:
            names.append(item.find('a', {'class': "item-title"}).text.strip('\n').strip(' ').strip('\n'))
            for price in item.find_all('li', {'class': 'price-current'}):
                prices.append(''.join([price.strong.text.strip(), price.sup.text.strip()]))

        #Zipping the prices and names together.
        items_prices = zip(prices, names)

        #Printing the item number, price, and name of the item.
        global cc_stock_table 
        cc_stock_table = [] 
        for n, (price, item) in enumerate(items_prices):
            print('Item#{n}: {p} : {i}'.format(n=n+1, p=price, i=item))
        sleep(scrape_refresh)

