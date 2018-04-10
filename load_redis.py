import json
from redis import StrictRedis
from rdflib.store import Store
from rdflib.namespace import SKOS
from rdflib_sqlalchemy import registerplugins
from flask import Flask
from rdflib import plugin, ConjunctiveGraph, Literal, URIRef
from config import DevelopmentConfig
import logging

registerplugins()

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

logger = logging.getLogger(__name__)
logging.basicConfig()

REDIS_HOST = app.config.get('REDIS_HOST', None)
REDIS_PORT = app.config.get('REDIS_PORT', None)
REDIS_DB = app.config.get('REDIS_DB', None)
identifier = URIRef(app.config.get('IDENTIFIER', None))
db_uri = Literal(app.config.get('DB_URI'))
store = plugin.get("SQLAlchemy", Store)(identifier=identifier, configuration=db_uri)
graph = ConjunctiveGraph(store)
graph.open(db_uri, create=False)
graph.bind('skos', SKOS)

rdb = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, charset="utf-8", decode_responses=True)

query = """select ?subject
            where { ?subject a <http://www.w3.org/2004/02/skos/core#Concept> . } """

res = graph.query(query)

labels = {}
for r in res:
    for lang in ['ar', 'zh', 'en', 'fr', 'ru', 'es']:
        label = graph.preferredLabel(r[0], lang=lang)
        if len(label):
            labels[lang] = str(label[0][1])
    data = json.dumps(labels)
    rdb.set(str(r[0]), data)
    labels = {}
