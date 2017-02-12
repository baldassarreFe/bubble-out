import urllib.request, urllib.parse, urllib.error
import random
import json
import os
import threading
import requests
import time

from flask import Flask
from flask import request
from flask import make_response

from bs4 import BeautifulSoup
from urllib.request import urlopen

# Flask app should start in global layout
app = Flask(__name__)

@app.route('/', methods=['GET','POST'])
def hello():
    return 'I''m alive'

@app.route('/webhook', methods=['POST'])
def webhook():
    # Receive request and parse it, this is the format
    # https://docs.api.ai/docs/webhook#section-sample-request-to-the-service
    req = request.get_json(silent=True, force=True)
    print('Request:\n', json.dumps(req, indent=4))

    # Process the query
    res = myProcessRequest(req)
    print('Response: \n', json.dumps(res, indent=4))

    # Send the response as json string in this format
    # https://docs.api.ai/docs/webhook#section-sample-response-from-the-service
    response = make_response(json.dumps(res))
    response.headers['Content-Type'] = 'application/json'
    return response

def myProcessRequest(req):
    if req.get('result').get('action') != 'analyze-article':
        return {}

    sessionId = req.get('sessionId')
    parameters = req.get('result').get('parameters')
    url = parameters.get('url')

    soup = BeautifulSoup(urlopen(url), 'lxml')
    title = soup.title.string

    if title:
        text = random.choice(list(map(lambda x: x.format(title = title),
            ['Sure, give me a second to read "{title}"',
                'Nice: "{title}" I\'ll read it in a moment ;)',
                'Mmm... "{title}" Have you seen my glasses?',
                'Interesting! Let me have a look to this "{title}"'
            ])))
        # threading.Thread(target=analyzeArticle, args=[sessionId, url], daemon=True).start()
    else:
        text = 'Sorry, I can\'t read this now'

    return {
        'speech': text,
        'displayText': text,
        # 'data': data,
        # 'contextOut': [],
        'source': 'bubble-out-prototype'
    }

def analyzeArticle(sessionId, url):
    time.sleep(3)
    headers = {
        'Authorization': 'Bearer ' + os.environ['API_AI_KEY'],
        'Content-Type': 'application/json',
        'charset': 'utf-8'
    }
    payload = {
        'event': 'write-back',
        'data': {
            'message':'Some time later...'
        },
        'sessionId': sessionId,
        'lang':'en',
        'v': '20150910'

    }
    requests.post('https://api.api.ai/v1/query/', json=payload, headers=headers)

def processRequest(req):
    if req.get('result').get('action') != 'analyze-article':
        return {}
    baseurl = 'https://query.yahooapis.com/v1/public/yql?'
    yql_query = makeYqlQuery(req)
    if yql_query is None:
        return {}
    yql_url = baseurl + urllib.parse.urlencode({'q': yql_query}) + '&format=json'
    result = urllib.request.urlopen(yql_url).read()
    data = json.loads(result)
    res = makeWebhookResult(data)
    return res


def makeYqlQuery(req):
    result = req.get('result')
    parameters = result.get('parameters')
    city = parameters.get('geo-city')
    if city is None:
        return None

    return "select * from weather.forecast where woeid in (select woeid from geo.places(1) where text='" + city + "')"


def makeWebhookResult(data):
    query = data.get('query')
    if query is None:
        return {}

    result = query.get('results')
    if result is None:
        return {}

    channel = result.get('channel')
    if channel is None:
        return {}

    item = channel.get('item')
    location = channel.get('location')
    units = channel.get('units')
    if (location is None) or (item is None) or (units is None):
        return {}

    condition = item.get('condition')
    if condition is None:
        return {}

    # print(json.dumps(item, indent=4))

    speech = 'Today in ' + location.get('city') + ': ' + condition.get('text') + \
             ', the temperature is ' + condition.get('temp') + ' ' + units.get('temperature')

    print('Response:')
    print(speech)

    return {
        'speech': speech,
        'displayText': speech,
        # 'data': data,
        # 'contextOut': [],
        'source': 'apiai-weather-webhook-sample'
    }


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print('Starting app on port %d' % port)
    app.run(debug=False, port=port, host='0.0.0.0')
