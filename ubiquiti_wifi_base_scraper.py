from bs4 import BeautifulSoup
from urllib.request import urlopen as uReq
import re
import smtplib
import logging
from time import time, sleep
import datetime

# This is a way to read a file and assign the values to variables without keeping a users email and password in the script. 
with open('email_settings.txt', 'rt') as file:
    for line in file:
        if line.startswith("sender:"):  
            sender_email = line.strip().split()[1:]
        elif line.startswith("receiver:"): 
            receiver_email = line.strip().split()[1:]
        elif line.startswith("password:"):
            password = line.strip().split()[1:]              

# Set a timer for how often to pull new status (seconds)
scrape_refresh = 300

# Begin the loop 
while True: 
    # Define the stock  condition
    in_stock = False

# This is the email that will be sent to the user when the product is in stock.
    if in_stock == True:
        subject = "IMPORTANT NOTIFICATION: Your Ubiquiti WIFI device is now in stock"
        body = "Important Notification\n\nHello,\n\nYour Ubiquiti WIFI device is now in stock.\n\n Please check https://ca.store.ui.com/ca/en/collections/unifi-network-wireless/products/unifi-wifi-basestation-xg"
        message = f"Subject: {subject}\n\n{body}"

        # Send the email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message)

    # Make a GET request to the webpage and parse the HTML with BeautifulSoup
    uClient = uReq('https://ca.store.ui.com/ca/en/collections/unifi-network-wireless/products/unifi-wifi-basestation-xg')
    page_html = uClient.read()
    uClient.close()

# Parsing the HTML code and converting it to text.
    soup = BeautifulSoup(page_html, 'html.parser')
    page_text = soup.get_text().lower()
    soup_text = str(soup)

# Using the regex to pull the info 
    item = re.findall(rf'<title>(.*?)</title', soup_text)
    status = re.findall(rf'"status":(.*?),', soup_text)
    price = re.findall(rf'"amount":(.*?),', soup_text)


    # Check if the product is in stock based on the text in soup text, re.findall is returning a list of 2 results, the first will suffice 
    in_stock = 'SoldOut' not in status[0]
    
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


    # Print the stock status of the UniFi WiFi BaseStation XG
    if in_stock:
        print("The UniFi WiFi BaseStation XG is in stock.")
        logging.info('Stock Check continues to run.\n')
    else:
        print("The UniFi WiFi BaseStation XG is out of stock.")
        logging.info('Stock Check continues to run.\n')

  # A timer that will refresh the page every 300 seconds.
    sleep(scrape_refresh)