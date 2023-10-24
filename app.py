from flask import Flask, jsonify, request, Response
import pandas as pd
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

import time

app = Flask(__name__)

@app.route('/')
def hello_world():
    return jsonify({"message": "Hello, World!"}), 200

if __name__ == '__main__':
    print("App starting!!!")
    print("App starting!!!")
    print("App starting!!!")
    print("App starting!!!")

    while True:
        current_time = time.strftime("%H:%M:%S")
        print(f"[{current_time}] This message will be logged every 1 second.")
        time.sleep(1)
    app.run()