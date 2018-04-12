import json
from redis import StrictRedis
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
rdb = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, charset="utf-8", decode_responses=True)

# delete everything in this redis database
rdb.flushdb()

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
    rdb.set(str(r[0]), data)
    labels = {}
    if i % 50 == 0:
        print("{} documents processed".format(i))
