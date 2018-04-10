import re
from math import ceil
from rdflib import plugin, ConjunctiveGraph, Literal, Namespace, URIRef, RDF
from rdflib.store import Store
from rdflib.namespace import SKOS
from rdflib_sqlalchemy import registerplugins
from flask import Flask
from flask import render_template, abort, request
from config import DevelopmentConfig
from elasticsearch import Elasticsearch
import logging

registerplugins()

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

logger = logging.getLogger(__name__)
logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

identifier = URIRef(app.config.get('IDENTIFIER', None))
db_uri = Literal(app.config.get('DB_URI'))
PER_PAGE = app.config.get("PER_PAGE", 20)
store = plugin.get("SQLAlchemy", Store)(identifier=identifier, configuration=db_uri)
graph = ConjunctiveGraph(store)
graph.open(db_uri, create=False)
graph.bind('skos', SKOS)


EU = Namespace('http://eurovoc.europa.eu/schema#')
UNBIST = Namespace('http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#')
ROUTABLES = {
    'Concept': SKOS.Concept,
    'ConceptScheme': SKOS.ConceptScheme,
    'Domain': EU.Domain,
    'MicroThesaurus': EU.MicroThesaurus,
    'GeographicTerm': UNBIST.GeographicTerm,
}


class Pagination(object):

    def __init__(self, page, per_page, total_count):
        self.page = page
        self.per_page = per_page
        self.total_count = total_count

    @property
    def pages(self):
        return int(ceil(self.total_count / float(self.per_page)))

    @property
    def has_prev(self):
        return int(self.page) > 1

    @property
    def has_next(self):
        return int(self.page) < int(self.pages)

    def iter_pages(self, left_edge=2, left_current=2,
                   right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > int(self.page) - int(left_current) - 1 and
                num < int(self.page) + int(right_current)) or \
               num > int(self.pages) - int(right_edge):
                if last + 1 != num:
                    yield None
                yield num
                last = num


@app.route('/')
def index():
    page = request.args.get('page')
    if not page:
        page = 1
    preferred_language = request.args.get('lang')
    if not preferred_language:
        preferred_language = 'en'
    if request.args.get('aspect'):
        aspect = request.args.get('aspect', None)
    else:
        aspect = 'MicroThesaurus'
    try:
        aspect_uri = ROUTABLES[aspect]
    except KeyError:
        aspect_uri = ROUTABLES['MicroThesaurus']

    results = []
    count_q = """select (count(distinct ?subject) as ?count)
                where { ?subject a <%s> .}
    """ % str(aspect_uri)
    count = 0
    res = graph.query(count_q)
    for r in res:
        count = int(r[0])

    # FIXME: This query takes way too long
    q = """ select ?subject ?prefLabel
            where { ?subject a <%s> .
            ?subject skos:prefLabel ?prefLabel .
            FILTER (lang(?prefLabel) = '%s') . }
            order by ?prefLabel
            LIMIT %s OFFSET %s""" % (
                str(aspect_uri), preferred_language, int(PER_PAGE), (int(page) - 1) * int(PER_PAGE))

    try:
        for res in graph.query(q):
            # r = Resource(graph, res)
            res_label = res[1]
            base_uri = ''
            uri_anchor = ''
            m = re.search('#', res[0])
            if m:
                base_uri, uri_anchor = res[0].split('#')
            else:
                base_uri = res[0]
            results.append({
                'base_uri': base_uri,
                'uri_anchor': uri_anchor,
                'pref_label': res_label})

    except Exception as e:
        logger.error("Caught Fatal Exception : {} ".format(e))
        abort(500)

    sorted_results = sorted(results, key=lambda tup: tup['pref_label'])
    pagination = Pagination(page, PER_PAGE, count)

    return render_template("index.html",
        context=sorted_results,
        lang=preferred_language,
        aspect=aspect,
        page=page,
        pagination=pagination)


@app.route('/term')
def term():
    preferred_language = request.args.get('lang')
    uri_anchor = request.args.get('uri_anchor')
    base_uri = request.args.get('base_uri')
    if not base_uri:
        logger.error("Forgot to pass base uril to term view!")
        abort(404)

    uri = base_uri
    if uri_anchor:
        uri = base_uri + '#' + uri_anchor
    pref_label = get_preferred_label(URIRef(uri), preferred_language)
    pref_labels = graph.preferredLabel(URIRef(uri))
    breadcrumbs = []
    breadcrumbs_q = """
            prefix skos: <http://www.w3.org/2004/02/skos/core#>
            prefix eu: <http://eurovoc.europa.eu/schema#>
            select ?domain ?microthesaurus where
            {
                {  ?domain skos:hasTopConcept ?microthesaurus . ?microthesaurus skos:narrower <%s> . }
            union
                { ?domain rdf:type eu:Domain . ?domain skos:hasTopConcept <%s> . }
            }
            """ % (uri, uri)
    for res in graph.query(breadcrumbs_q):
        bc = {}
        bc.update({'domain': {'uri': res.domain, 'pref_label': get_preferred_label(res.domain, preferred_language)}})
        if res.microthesaurus:
            bc.update({
                'microthesaurus':
                {'uri': res.microthesaurus,
                'pref_label': get_preferred_label(res.microthesaurus, preferred_language)}})
        breadcrumbs.append(bc)

    scope_notes = []
    sns = graph.objects(subject=URIRef(uri), predicate=SKOS.scopeNote)
    for s in sns:
        if s.language == preferred_language:
            scope_notes.append(s)

    alt_labels = []
    als = graph.objects(subject=URIRef(uri), predicate=SKOS.altLabel)
    for a in als:
        if a.language == preferred_language:
            alt_labels.append(a)

    relationships = []
    for c in [SKOS.broader, SKOS.related, SKOS.narrower, SKOS.member]:
        this_results = []
        for rel in graph.objects(subject=URIRef(uri), predicate=c):
            rel_label = get_preferred_label(rel, preferred_language)
            this_results.append({'type': c.split('#')[1], 'uri': rel, 'pref_label': rel_label})
        sorted_results = sorted(this_results, key=lambda tup: tup['pref_label'])
        for sr in sorted_results:
            relationships.append(sr)

    matches = []
    for t in [SKOS.relatedMatch, SKOS.broadMatch, SKOS.closeMatch, SKOS.exactMatch, SKOS.narrowMatch]:
        matches_q = """ PREFIX owl: <http://www.w3.org/2002/07/owl#>
            select ?%s where
            { <%s> owl:sameAs ?osa . ?%s <%s> ?osa }""" % (
                t.split('#')[1], uri, t.split('#')[1], t)

        for m in graph.query(matches_q):
            matches.append({'type': t.split('#')[1], 'uri': m})

    rdf_types = []
    for t in graph.objects(subject=URIRef(uri), predicate=RDF.type):
        rdf_types.append({'short_name': t.split('#')[1], 'uri': t})

    return render_template('term.html',
        rdf_types=rdf_types,
        pref_label=pref_label,
        pref_labels=pref_labels,
        alt_labels=alt_labels,
        breadcrumbs=breadcrumbs,
        scope_notes=scope_notes,
        relationships=relationships,
        matches=matches,
        lang=preferred_language)


@app.route('/search')
def search():
    query = request.args.get('q', None)
    if not query:
        logging.error("Forgot to pass query to search view!")
        abort(500)
    preferred_language = request.args.get('lang')
    if not preferred_language:
        preferred_language = 'en'

    elasticsearch_uri = app.config.get('ELASTICSEARCH_URI', None)
    index_name = app.config.get('INDEX_NAME', None)
    es = Elasticsearch(elasticsearch_uri)

    match = es.search(index=index_name, q=query)
    if len(match) == 0:
        resp = ["No Matches"]
        return render_template('search.html', results=resp)
    resp = []
    for m in match['hits']['hits']:
        resp.append({
            # 'score': m['_score'],
            'pref_label': get_preferred_label(URIRef(m["_source"]["uri"]), preferred_language),
            'uri': m["_source"]["uri"],
        }
        )

    return render_template('search.html', results=resp, lang=preferred_language)


def get_preferred_label(resource, language):
    default_language = app.config.get('LANGUAGE_CODE')
    if not language:
        language = default_language
    label = graph.preferredLabel(resource, lang=language)
    if len(label) > 0:
        return label[0][1]
    else:
        label = graph.preferredLabel(resource, lang=default_language)
        if len(label) > 0:
            return label[0][1]
        else:
            return resource
