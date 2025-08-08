from flask import Flask, jsonify
from metrics import get_metrics

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    return jsonify(get_metrics())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)