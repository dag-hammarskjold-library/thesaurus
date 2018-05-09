import sys
import json
from redis import StrictRedis
from redis.exceptions import RedisError
from rdflib.store import Store
from rdflib.namespace import SKOS
from rdflib_sqlalchemy import registerplugins
from flask import Flask
from rdflib import plugin, ConjunctiveGraph, Literal, URIRef
from config import DevelopmentConfig

registerplugins()

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

# get config for sqlalchemy and create graph object
identifier = URIRef(app.config.get('IDENTIFIER', None))
db_uri = Literal(app.config.get('DB_URI'))
store = plugin.get("SQLAlchemy", Store)(identifier=identifier, configuration=db_uri)
graph = ConjunctiveGraph(store)
graph.open(db_uri, create=False)
graph.bind('skos', SKOS)

# get config for redis and connect
REDIS_HOST = app.config.get('REDIS_HOST', None)
REDIS_PORT = app.config.get('REDIS_PORT', None)
REDIS_DB = app.config.get('REDIS_DB', None)
REDIS_TIMEOUT = app.config.get('REDIS_TIMEOUT', None)
try:
    rdb = StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        charset="utf-8",
        decode_responses=True,
        socket_timeout=REDIS_TIMEOUT,
        socket_connect_timeout=REDIS_TIMEOUT)
except RedisError as e:
    print("Could not connect to redis service, exiting")
    sys.exit(1)
except Exception as e:
    print("Could not connect to redis service: {}, exiting".format(e))
    sys.exit(1)


# delete everything in this redis database
try:
    rdb.flushdb()
except RedisError as e:
    print("Could not delete old db, exiting!")
    sys.exit(1)


# get all SKOS.Concept uri's (except place names)
query = """
    prefix unbist: <http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#>
    select ?uri
    where
    { ?uri rdf:type skos:Concept filter not exists { ?uri rdf:type unbist:PlaceName } . }"""

res = graph.query(query)

# get all prefLabels for SKOS.Concept URIs
# store URI -> json.dumps({'ar': prefLabel, 'zh': prefLabel, 'en': prefLabel ...})
# to retrieve: data = redis.get(uri), dict=json.loads(data)
labels = {}
i = 0
for r in res:
    i += 1
    for lang in ['ar', 'zh', 'en', 'fr', 'ru', 'es']:
        label = graph.preferredLabel(r[0], lang=lang)
        if len(label):
            labels[lang] = str(label[0][1])
    data = json.dumps(labels)
    try:
        rdb.set(str(r[0]), data)
    except RedisError as e:
        print("Loading Cache failed for : {}, {}".format(str(r[0]), e))
    labels = {}
    if i % 50 == 0:
        print("{} documents processed".format(i))
