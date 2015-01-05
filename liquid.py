import condense
from flask import Flask, Response, request

app = Flask(__name__, static_folder='', static_url_path='')


@app.route("/sales")
def sales():
    refresh = request.args.get('refresh')
    return Response(condense.get_sales(refresh),  mimetype='application/json')


@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == "__main__":
    app.run(debug=True)
