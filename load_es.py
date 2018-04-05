import sys
# from urllib.request import Request, urlopen
import requests
import json
from flask import Flask
from config import DevelopmentConfig
from rdflib import plugin, ConjunctiveGraph, Namespace, Literal, URIRef
from rdflib.store import Store
from rdflib_sqlalchemy import registerplugins
from rdflib.namespace import SKOS

registerplugins()


app = Flask(__name__)

app.config.from_object(DevelopmentConfig)

identifier = URIRef(app.config.get('IDENTIFIER', None))
db_uri = Literal(app.config.get('DB_URI'))

store = plugin.get("SQLAlchemy", Store)(identifier=identifier, configuration=db_uri)
graph = ConjunctiveGraph(store)
graph.open(db_uri, create=False)
graph.bind('skos', SKOS)

elasticsearch_uri = app.config.get('ELASTICSEARCH_URI', None)

EU = Namespace('http://eurovoc.europa.eu/schema#')
UNBIST = Namespace('http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#')

querystring = """prefix unbist: <http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#>
    select ?uri
    where
    { ?uri rdf:type skos:Concept filter not exists { ?uri rdf:type unbist:PlaceName } . }"""


thesaurus_index = {
    "settings": {
        "index": {
            "number_of_shards": 3
        }
    }
}


resp = requests.put("{}/thesaurus".format(elasticsearch_uri),
    data=json.dumps(thesaurus_index),
    headers={'Content-Type': 'application/json'})
if not resp.status_code == 200:
    print(resp.status_code)
    print(resp.reason)
    # print("error creating index: Aborting")
    # sys.exit(-1)

thesaurus_mapping = {
    "mappings": {
        "terms": {
            "properties": {
                "scope_notes": {"type": "string"},
                "uri": {"type": "string"},
                "alt_labels": {"type": "string"},
                "labels": {"type": "string"}
            }
        }
    }
}

resp = requests.put("{}/thesaurus".format(elasticsearch_uri),
    data=json.dumps(thesaurus_mapping),
    headers={'Content-Type': 'application/json'})

if not resp.status_code == 200:
    print(resp.status_code)
    print(resp.reason)
    print("error creating Mapping: Aborting")
    sys.exit(-1)

i = 1

for uri in graph.query(querystring):
    i += 1
    this_uri = uri[0]
    doc = {"uri": this_uri}
    pref_labels = []
    for label in graph.preferredLabel(URIRef(this_uri)):
        pref_labels.append(label[1])
    doc.update({"labels": pref_labels})

    alt_labels = []
    for label in graph.objects(URIRef(this_uri), SKOS.altLabel):
        alt_labels.append(label)
    doc.update({"alt_labels": alt_labels})

    scope_notes = []
    for sn in graph.objects(URIRef(this_uri), SKOS.scopeNote):
        scope_notes.append(sn)
    doc.update({"scope_notes": scope_notes})

    payload = json.dumps(doc)

    resp = requests.put("{}/thesaurus".format(elasticsearch_uri),
            data=payload,
            headers={'Content-Type': 'application/json'})
    if not resp .status_code == 200:
        print("Could not upload data.  Aborting")
        sys.exit(-1)
    if i % 50 == 0:
        print("{} documents indexed".format(i))
