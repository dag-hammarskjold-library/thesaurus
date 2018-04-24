import io
import json
from redis import StrictRedis
import re
from math import ceil
from rdflib import plugin, ConjunctiveGraph, Literal, Namespace, URIRef, RDF
from rdflib.store import Store
from rdflib.namespace import SKOS
from rdflib_sqlalchemy import registerplugins
from flask import Flask
from flask import render_template, abort, request, Response, send_file
from config import DevelopmentConfig
from elasticsearch import Elasticsearch

registerplugins()

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

# setup graph object
identifier = URIRef(app.config.get('IDENTIFIER', None))
db_uri = Literal(app.config.get('DB_URI'))
store = plugin.get("SQLAlchemy", Store)(identifier=identifier, configuration=db_uri)
graph = ConjunctiveGraph(store)
graph.open(db_uri, create=False)
graph.bind('skos', SKOS)

# setup redis connection
PER_PAGE = app.config.get("PER_PAGE", 20)
REDIS_HOST = app.config.get('REDIS_HOST', None)
REDIS_PORT = app.config.get('REDIS_PORT', None)
REDIS_DB = app.config.get('REDIS_DB', None)
rdb = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, charset="utf-8", decode_responses=True)

# setup Elasticsearch connection
elasticsearch_uri = app.config.get('ELASTICSEARCH_URI', None)
index_name = app.config.get('INDEX_NAME', None)
es = Elasticsearch(elasticsearch_uri)

EU = Namespace('http://eurovoc.europa.eu/schema#')
DCTERMS = Namespace("http://purl.org/dc/terms#")
UNBIST = Namespace('http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#')
ROUTABLES = {
    'Concept': SKOS.Concept,
    'ConceptScheme': SKOS.ConceptScheme,
    'Domain': EU.Domain,
    'MicroThesaurus': EU.MicroThesaurus
}


class Pagination:
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


class Term:
    def __init__(self, concept, lang='en'):
        """
        @concept in a concept URI, e.g.
        https://metadata.un.org/thesaurus#1000463

        @lang is the preferred language of the interface
        """
        self.concept = concept
        self.lang = lang

    @property
    def preferred_language(self):
        return self.lang

    def preferred_label(self):
        return get_preferred_label(self.concept, self.lang)

    def preferred_labels(self):
        return graph.preferredLabel(self.concept)

    def notes(self):
        notes = []
        for rel in graph.objects(subject=URIRef(self.concept), predicate=SKOS.note):
            notes.append(rel)
        return notes

    def scheme(self):
        scheme = []
        q = "select ?scheme where { <%s> skos:inScheme ?scheme .}" % self.concept
        res = graph.query(q)
        for r in res:
            scheme.append(r)
        return scheme

    def identifier(self):
        ident = []
        q = "select ?id where { <%s> dcterms:identifier ?id .}" % self.concept
        res = graph.query(q)
        for r in res:
            ident.append(r)
        return ident

    def top_concept_of(self):
        c = []
        q = "select ?id where { <%s> skos:hasTopConcept ?id . }" % self.concept
        res = graph.query(q)
        for r in res:
            c.append(r)
        return c

    def title(self):
        title = []
        q = "select ?id where { <%s> dcterms:title ?id .}" % self.concept
        res = graph.query(q)
        for r in res:
            title.append(r)
        return title

    def breadcrumbs(self):
        """
        get breadcumbs when a user clicks on a concept
        """
        breadcrumbs = []
        breadcrumbs_q = """
            prefix skos: <http://www.w3.org/2004/02/skos/core#>
            select ?domain ?microthesaurus where
            {
                {  ?domain skos:hasTopConcept ?microthesaurus . ?microthesaurus skos:narrower <%s> . }
            union
                { ?domain rdf:type eu:Domain . ?domain skos:hasTopConcept <%s> . }
            }
            """ % (self.concept, self.concept)
        for res in graph.query(breadcrumbs_q):
            bc = {}
            bc.update(
                {'domain':
                    {'uri': res.domain, 'pref_label': get_preferred_label(res.domain, self.lang)}})
            if res.microthesaurus:
                bc.update(
                    {'microthesaurus':
                        {'uri': res.microthesaurus,
                        'pref_label': get_preferred_label(res.microthesaurus, self.lang)}})
            breadcrumbs.append(bc)
        return breadcrumbs

    def scope_notes(self):
        """
        display scope notes (if avalable)
        for a concept
        """
        scope_notes = []
        sns = graph.objects(subject=URIRef(self.concept), predicate=SKOS.scopeNote)
        for s in sns:
            if s.language == self.lang:
                scope_notes.append(s)
        return scope_notes

    def alt_labels(self):
        """
        if alternative lables exist
        for this concept in the given language
        display them
        """
        alt_labels = []
        als = graph.objects(subject=URIRef(self.concept), predicate=SKOS.altLabel)
        for a in als:
            if a.language == self.lang:
                alt_labels.append(a)
        return alt_labels

    def relationships(self):
        """
        given a concept get all related,
        broader and narrower terms
        """
        relationships = []
        for c in [SKOS.broader, SKOS.related, SKOS.narrower, SKOS.member]:
            this_results = []
            for rel in graph.objects(subject=URIRef(self.concept), predicate=c):
                rel_label = get_preferred_label(rel, self.lang)
                this_results.append({'type': c.split('#')[1], 'uri': rel, 'pref_label': rel_label})
            sorted_results = sorted(this_results, key=lambda tup: tup['pref_label'])
            for sr in sorted_results:
                relationships.append(sr)
        return relationships

    def matches(self):
        """
        punt for now
        """
        matches = []
        matches_q = """
            prefix skos: <http://www.w3.org/2004/02/skos/core#>
            select ?exactmatch where
            {
            <%s> dcterms:identifier ?identifier . ?identifier skos:exactMatch ?exactMatch
            }""" % self.concept
        # matches_q = """select ?evTerm where { ?evTerm skos:exactMatch ?id . ?unbisTerm dcterms:identifier ?id }"""

        for m in graph.query(matches_q):
            matches.append({'uri': m})
        return matches

    def rdf_types(self):
        """
        get the rdf types for this term
        1 or more of concept, MicroThesaurus, etc
        """
        rdf_types = []
        for t in graph.objects(subject=URIRef(self.concept), predicate=RDF.type):
            rdf_types.append({'short_name': t.split('#')[1], 'uri': t})
        return rdf_types

    def language_labels(self):
        """
        get and order concept translations
        """
        labels = []
        for lang in ['ar', 'zh', 'en', 'fr', 'ru', 'es']:
            labels.append(graph.preferredLabel(URIRef(self.concept), lang=lang))
        return labels


@app.errorhandler(400)
def custom400(error):
    response = 'ERROR: ' + error.description['message']
    return response


@app.route('/')
def index():
    page = request.args.get('page')
    if not page:
        page = 1
    preferred_language = request.args.get('lang')
    if not preferred_language:
        preferred_language = 'en'
    aspect = request.args.get('aspect', 'MicroThesaurus')

    try:
        aspect_uri = ROUTABLES[aspect]
    except KeyError as e:
        app.logger.error("Caught exception : {}".format(e))
    aspect_uri = ROUTABLES['MicroThesaurus']

    # if listing SKOS Concepts
    # use redis store
    if aspect == 'Concept':
        return get_concepts(page, preferred_language)

    results = []
    count_q = """select (count(distinct ?subject) as ?count)
                where { ?subject a <%s> .}
    """ % str(aspect_uri)
    count = 0
    res = graph.query(count_q)
    for r in res:
        count = int(r[0])

    q = """ select ?subject ?prefLabel
        where { ?subject a <%s> .
        ?subject skos:prefLabel ?prefLabel .
        FILTER (lang(?prefLabel) = '%s') . }
        order by ?prefLabel
        LIMIT %s OFFSET %s""" % (
            str(aspect_uri), preferred_language, int(PER_PAGE), (int(page) - 1) * int(PER_PAGE))

    for res in graph.query(q):
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

    pagination = Pagination(page, PER_PAGE, count)

    return render_template("index.html",
        context=results,
        lang=preferred_language,
        aspect=aspect,
        page=page,
        pagination=pagination)


@app.route('/term')
def term():
    page = request.args.get('page', '1')
    preferred_language = request.args.get('lang', 'en')
    uri_anchor = request.args.get('uri_anchor')
    base_uri = request.args.get('base_uri')
    if not base_uri:
        app.logger.error("Forgot to pass base uri to term view!")
        abort(404)

    uri = base_uri
    if uri_anchor:
        uri = base_uri + '#' + uri_anchor

    term = Term(uri, preferred_language)

    relationships = term.relationships()
    count = len(relationships)
    rel = relationships[(int(page) - 1) * int(PER_PAGE):(int(page) - 1) * int(PER_PAGE) + int(PER_PAGE)]
    pagination = Pagination(page, PER_PAGE, count)

    return render_template('term.html',
        rdf_types=term.rdf_types(),
        pref_label=term.preferred_label(),
        pref_labels=term.language_labels(),
        alt_labels=term.alt_labels(),
        breadcrumbs=term.breadcrumbs(),
        scope_notes=term.scope_notes(),
        relationships=rel,
        matches=term.matches(),
        lang=preferred_language,
        pagination=pagination)


@app.route('/search')
def search():
    query = request.args.get('q', None)
    if not query:
        app.logger.error("Forgot to pass query to search view!")
        abort(500)
    preferred_language = request.args.get('lang', None)
    if not preferred_language:
        app.logger.error("No language set in search view!")
        abort(500)
    page = request.args.get('page', '1')

    match = es.search(
        index=index_name,
        q=query,
        size=50,
        _source=['labels_{}'.format(preferred_language), 'uri'])
    count = len(match)
    if count == 0:
        resp = ["No Matches"]
        return render_template('search.html', results=resp, lang=preferred_language)
    response = []
    for m in match['hits']['hits']:
        response.append({
            'score': m['_score'],
            'pref_label': get_preferred_label(URIRef(m["_source"]["uri"]), preferred_language),
            'uri': m["_source"]["uri"]
        }
        )
    resp = response[(int(page) - 1) * int(PER_PAGE):(int(page) - 1) * int(PER_PAGE) + int(PER_PAGE)]
    pagination = Pagination(page, PER_PAGE, len(response))

    return render_template(
        'search.html',
        results=resp,
        query=query,
        lang=preferred_language,
        pagination=pagination)


@app.route('/autocomplete')
def autocomplete():
    q = request.args.get('q', None)
    preferred_language = request.args.get('lang', None)
    if not q:
        abort(500)
    if not preferred_language:
        abort(500)

    # match against label and alt label for
    # the preferred language
    # boost preferred label
    dsl_q = """
     {
       "query": {
         "multi_match" : {
           "query":    "%s",
           "fields": [ "labels_%s^3", "alt_labels_%s" ]
         }
       }
     }""" % (q, preferred_language, preferred_language)

    app.logger.debug("Looking at labels_{}".format(preferred_language))
    match = es.search(index='thesaurus', body=dsl_q, size=20)
    results = []
    for res in match["hits"]["hits"]:
        if not res["_source"].get("labels_%s" % preferred_language):
            continue
        pref_label = get_preferred_label(URIRef(res["_source"]["uri"]), preferred_language)
        base_uri = ''
        uri_anchor = ''
        m = re.search('#', res["_source"]["uri"])
        if m:
            base_uri, uri_anchor = res["_source"]["uri"].split('#')
        else:
            base_uri = res["_source"]["uri"][0]
        results.append({
            "base_uri": base_uri,
            "uri_anchor": uri_anchor,
            "pref_label": pref_label
        })

    return Response(json.dumps(results), content_type='application/json')


@app.route('/api', methods=['GET', 'POST'])
def serialize_data():
    uri_anchor = request.form.get('uri_anchor')
    base_uri = request.form.get('base_uri')

    req_format = request.form.get('format')
    target = request.form.get('dl_location')
    req_format = req_format.lower()
    if req_format.lower() not in ['xml',
        'n3', 'turtle', 'nt',
        'pretty-xml', 'trix',
            'trig']:
            abort(400, {"message": "Unsuported serialization format: {}".format(req_format)})

    if req_format == 'xml':
        req_format = 'pretty-xml'

    uri = base_uri + "#" + uri_anchor
    node = Literal(uri)
    term = Term(URIRef(uri))
    pref_labels = term.preferred_labels()
    scope_notes = term.scope_notes()
    alt_labels = term.alt_labels()
    in_scheme = term.scheme()
    notes = term.notes()
    scope_notes = term.scope_notes()
    related = term.relationships()
    identifier = term.identifier()

    from rdflib import Graph
    g = Graph()
    g.bind('skos', SKOS)

    g.add((node, RDF.type, SKOS.Concept))
    for l in pref_labels:
        g.add((node, SKOS.prefLabel, l[1]))
    for l in alt_labels:
        g.add((node, SKOS.altLabel, l))
    for l in in_scheme:
        g.add((node, SKOS.inScheme, URIRef(l[0])))
    for l in notes:
        g.add((node, SKOS.note, l))
    for l in scope_notes:
        g.add((node, SKOS.scopeNote, l))
    for l in related:
        if l.get('type') == 'broader':
            g.add((node, SKOS.broader, URIRef(l.get('uri'))))
        elif l.get('type') == 'narrower':
            g.add((node, SKOS.narrower, URIRef(l.get('uri'))))
        elif l.get('type') == 'related':
            g.add((node, SKOS.related, URIRef(l.get('uri'))))
        elif l.get('type') == 'member':
            g.add((node, SKOS.member, URIRef(l.get('uri'))))

    app.logger.info("================================= {} ======================".format(identifier))
    if(len(identifier)):
        g.add((node, DCTERMS.identifier, identifier[0][0]))
        g.add((node, DCTERMS.identifier, URIRef(identifier[1][0])))

    data = g.serialize(format=req_format, encoding='utf-8')

    file_ext = ''
    if req_format == 'turtle':
        file_ext = 'ttl'
    elif req_format == 'pretty-xml':
        file_ext = 'xml'
    else:
        file_ext = req_format

    as_attachment = None
    if target == "download":
        as_attachment = True
    else:
        as_attachment = False

    return send_file(
        io.BytesIO(data),
        attachment_filename='{}.{}'.format(uri_anchor, file_ext),
        as_attachment=as_attachment
    )


def get_preferred_label(resource, language):
    default_language = app.config.get('LANGUAGE_CODE')
    if not language:
        language = default_language
    label = graph.preferredLabel(resource, lang=language)
    if len(label) > 0:
        return label[0][1]
    else:
        return resource


def get_pref_label_concept(concept_uri, language='en'):
    '''
    get prefLabel for a concept
    @args:
    :concept_uri: uri of concept -- this will only work
        for SKOS.Concept items
    :language: one of ar, zh, en, fr, ru, es
    get prefLabel from redis store
    '''
    vals = rdb.get(concept_uri)
    data = json.loads(vals)
    return data.get(language, None)


def get_concepts(page, lang='en'):
    '''
    @args
        page: requested page number
        lang: requested language parameter
    get all concept uir's and prefLabels
    sort on prefLabels
    this method is seperate from index (above)
    because rdflib-sqlalchemy is basically
    useless for triple store

    Need all concepts and prefLabels
    so that sorting makes sense
    '''
    num_concepts = 0
    q = """select (count(distinct ?subject) as ?count)
            where { ?subject a <%s> .} """ % str(SKOS.Concept)
    res = graph.query(q)
    for r in res:
        num_concepts = int(r[0])

    q = """ select ?subject
        where { ?subject a <%s> . }
        """ % str(SKOS.Concept)

    results = []
    uris = graph.query(q)
    for uri in uris:
        pref_label = get_pref_label_concept(str(uri[0]), lang)
        if not pref_label:
            continue
        base_uri = ''
        uri_anchor = ''
        m = re.search('#', uri[0])
        if m:
            base_uri, uri_anchor = uri[0].split('#')
        else:
            base_uri = uri[0]
        results.append({
            'base_uri': base_uri,
            'uri_anchor': uri_anchor,
            'pref_label': pref_label})

    sorted_results = sorted(results, key=lambda tup: tup['pref_label'])
    pagination = Pagination(page, PER_PAGE, num_concepts)
    response = sorted_results[
        (int(page) - 1) * int(PER_PAGE):(int(page) - 1) * int(PER_PAGE) + int(PER_PAGE)]

    return render_template("index.html",
        context=response,
        lang=lang,
        aspect="Concept",
        page=page,
        pagination=pagination)
