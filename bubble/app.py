import urllib.request, urllib.parse, urllib.error
import random
import json
import os
import threading
import requests
import time
import datetime

from flask import Flask
from flask import request
from flask import make_response

from watson_developer_cloud import AlchemyLanguageV1
from watson_developer_cloud import PersonalityInsightsV3

from bs4 import BeautifulSoup
from urllib.request import urlopen

# Flask app should start in global layout
app = Flask(__name__)

alchemy_language = AlchemyLanguageV1(api_key = os.environ['ALCHEMY_API_KEY'])
personality_insights = PersonalityInsightsV3(
    version = '2016-10-20',
    username = os.environ['PERSONALITY_API_USER'],
    password = os.environ['PERSONALITY_API_PWD'])

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
    facebookId = req.get('originalRequest').get('data').get('sender').get('id')
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
        threading.Thread(target=analyzeArticle, args=[facebookId, url], daemon=True).start()
        threading.Thread(target=analyzePersonality, args=[facebookId, url], daemon=True).start()
        # threading.Thread(target=analyzeArticle2, args=[sessionId, url], daemon=True).start()
    else:
        text = 'Sorry, I can\'t read this now'

    return {
        'speech': text,
        'displayText': text,
        # 'data': data,
        # 'contextOut': [],
        'source': 'bubble-out-prototype'
    }

def analyzeArticle(facebookId, url):
    # Perform analysis
    combined_operations = ['keyword', 'author', 'concept', 'pub-date', 'doc-emotion']
    analysis = alchemy_language.combined(url=url,
        # sentiment=1,
        extract=combined_operations)

    keywords = [kw.get('text') for kw in analysis.get('keywords')
        if float(kw.get('relevance'))>0.55]
    concepts = [c.get('text') for c in analysis.get('concepts')
        if float(c.get('relevance'))>0.55]
    publicationDate = datetime.datetime.strptime(
        analysis.get('publicationDate').get('date'),
        '%Y%m%dT%H%M%S')
    emotions = [e for e in  analysis.get('docEmotions')
        if float(analysis.get('docEmotions').get(e))>0.3]
    author = analysis.get('author')

    message = 'I see you are reading an article by {author}, published on {publicationDate} which is about {concepts}... Interesting!'.format(
        author=author,
        publicationDate=publicationDate.strftime('%d %B %Y'),
        concepts=', '.join(concepts))

    sendFbMessage(facebookId, message)

# Send results back to facebook
def sendFbMessage(facebookId, message):
    params = {
        'access_token': os.environ['MESSENGER_PAGE_KEY']
    }
    headers = {
        'Content-Type': 'application/json',
        'charset': 'utf-8'
    }
    payload = {
      "recipient": {
        "id": facebookId
      },
      "message": {
        "text": message
      }
    }
    response = requests.post('https://graph.facebook.com/v2.6/me/messages', params=params, json=payload, headers=headers)
    if response.status_code != requests.codes.ok:
        print('Callback response:\n', json.dumps(response.json(), indent=4))

def analyzePersonality(facebookId, url):
    # textjson = alchemy_language.text(url=url)
    text = textjson.get('text')

    # profile = personality_insights.profile(
    #    text,
    #    raw_scores=True,
    #    consumption_preferences=True)

    message = 'Personality coming soon'

    sendFbMessage(facebookId, message)

def analyzeArticle2(sessionId, url):
    time.sleep(3)
    headers = {
        'Authorization': 'Bearer ' + os.environ['API_AI_KEY'],
        'Content-Type': 'application/json',
        'charset': 'utf-8'
    }
    payload = {
        'event': {
            'name': 'write-back',
            'data': {
                'message':'API Some time later...'
                }
        },
        'sessionId': sessionId,
        'lang':'en',
        'v': '20150910'
    }
    response = requests.post('https://api.api.ai/v1/query/', json=payload, headers=headers)
    if response.status_code != requests.codes.ok:
        print('Callback response:\n', json.dumps(response.json(), indent=4))

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

    print('Response:\n', speech)

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
