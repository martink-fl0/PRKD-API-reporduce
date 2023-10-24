from flask import Flask, jsonify, request, Response
import time

app = Flask(__name__)

@app.route('/')
def hello_world():
    return jsonify({"message": "Logging message when accessing root /"}), 200

if __name__ == '__main__':
    app.run()