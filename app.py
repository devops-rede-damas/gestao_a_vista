import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

from services.movidesk_api import get_tickets

load_dotenv()

app = Flask(__name__)


@app.route("/gv_movidesk")
def gv_movidesk():
    tickets = get_tickets()
    return render_template("gta.html", tickets=tickets)


@app.route("/api/tickets")
def api_tickets():
    return jsonify(get_tickets())


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 7001)),
        debug=os.getenv("FLASK_DEBUG", "True").lower() == "true",
    )
