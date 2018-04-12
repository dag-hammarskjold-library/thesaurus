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
        "uri": {"type": "text"},
        "scope_notes_ar": {"type": "text", "analyzer": "arabic"},
        "scope_notes_zh": {"type": "text", "analyzer": "chinese"},
        "scope_notes_en": {"type": "text", "analyzer": "english"},
        "scope_notes_fr": {"type": "text", "analyzer": "french"},
        "scope_notes_ru": {"type": "text", "analyzer": "russian"},
        "scope_notes_es": {"type": "text", "analyzer": "spanish"},
        "labels_ar": {"type": "text", "analyzer": "arabic"},
        "labels_zh": {"type": "text", "analyzer": "chinese"},
        "labels_en": {"type": "text", "analyzer": "english"},
        "labels_fr": {"type": "text", "analyzer": "french"},
        "labels_ru": {"type": "text", "analyzer": "russian"},
        "labels_es": {"type": "text", "analyzer": "spanish"},
        "alt_labels_ar": {"type": "text", "analyzer": "arabic"},
        "alt_labels_zh": {"type": "text", "analyzer": "chinese"},
        "alt_labels_en": {"type": "text", "analyzer": "english"},
        "alt_labels_fr": {"type": "text", "analyzer": "french"},
        "alt_labels_ru": {"type": "text", "analyzer": "russian"},
        "alt_labels_es": {"type": "text", "analyzer": "spanish"},
        "created": {
            "type": "date",
            "format": "strict_date_optional_time||epoch_millis"
        }
    }
}

print("creating mapping ...")
res = es_con.indices.put_mapping(index=index_name, doc_type="doc", body=thesaurus_mapping)
print("resonse: {}".format(res))

i = 1
for uri in graph.query(querystring):
    this_uri = uri[0]
    doc = {"uri": this_uri}
    j = 1
    for lang in ['ar', 'zh', 'en', 'fr', 'ru', 'es']:
        pref_labels = []
        for label in graph.preferredLabel(URIRef(this_uri), lang):
            pref_labels.append(label[1])
        doc.update({"labels_{}".format(lang): pref_labels})

        alt_labels = []
        for label in graph.objects(URIRef(this_uri), SKOS.altLabel):
            if label.language == lang:
                alt_labels.append(label)
        doc.update({"alt_labels_{}".format(lang): alt_labels})

        scope_notes = []
        for sn in graph.objects(URIRef(this_uri), SKOS.scopeNote):
            if sn.language == lang:
                scope_notes.append(sn)
        doc.update({"scope_notes_{}".format(lang): scope_notes})

        payload = json.dumps(doc)

        res = es_con.index(index=index_name, doc_type='doc', body=payload)
        doc = {"uri": this_uri}
        j = j + 1
    i += j
    if i % 50 == 0:
        print("{} documents indexed".format(i))
