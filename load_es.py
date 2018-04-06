import sys
# from urllib.request import Request, urlopen
import json
from flask import Flask
from config import DevelopmentConfig
from rdflib import plugin, ConjunctiveGraph, Namespace, Literal, URIRef
from rdflib.store import Store
from rdflib_sqlalchemy import registerplugins
from rdflib.namespace import SKOS
from elasticsearch import Elasticsearch

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
index_name = app.config.get('INDEX_NAME', None)
es_con = Elasticsearch(elasticsearch_uri)

EU = Namespace('http://eurovoc.europa.eu/schema#')
UNBIST = Namespace('http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#')

querystring = """
    prefix unbist: <http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#>
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

# Delete index if exists
if es_con.indices.exists(index_name):
    print("deleting '%s' index..." % (index_name))
    res = es_con.indices.delete(index=index_name)
    print(" response: '%s'" % (res))

# Create Index
print("creating {} index...".format(index_name))
res = es_con.indices.create(index=index_name, body=thesaurus_index)
print(" response: {}".format(res))

thesaurus_mapping = {
    "properties": {
        "scope_notes": {"type": "text"},
        "uri": {"type": "text"},
        "alt_labels": {"type": "text"},
        "alt_labels_orig": {
            "type": "string",
            "index": "not_analyzed"
        },
        "labels": {"type": "text"},
        "labels_orig": {
            "type": "string",
            "index": "not_analyzed"
        },
        "created": {
            "type": "date",
            "format": "strict_date_optional_time||epoch_millis"
        }
    }
}

print("creating mapping ...")
res = es_con.indices.put_mapping(index=index_name, doc_type="mapping", body=thesaurus_mapping)
print("resonse: {}".format(res))

i = 1

for uri in graph.query(querystring):
    i += 1
    this_uri = uri[0]
    doc = {"uri": this_uri}
    pref_labels = []
    labels_orig_lc = []
    for label in graph.preferredLabel(URIRef(this_uri)):
        pref_labels.append(label[1])
        if label[1].language in ['en', 'fr', 'es']:
            labels_orig_lc.append(label[1].lower())
    doc.update({"labels": pref_labels})

    alt_labels = []
    alt_labels_orig_lc = []
    for label in graph.objects(URIRef(this_uri), SKOS.altLabel):
        alt_labels.append(label)
        if label.language in ['en', 'fr', 'es']:
            alt_labels_orig_lc.append(label.lower())
    doc.update({"alt_labels": alt_labels})
    doc.update({"alt_labels_orig": alt_labels + alt_labels_orig_lc})

    scope_notes = []
    for sn in graph.objects(URIRef(this_uri), SKOS.scopeNote):
        scope_notes.append(sn)
    doc.update({"scope_notes": scope_notes})

    payload = json.dumps(doc)

    res = es_con.index(index=index_name, doc_type='post', id=i, body=payload)
    if i % 50 == 0:
        print("{} documents indexed".format(i))
