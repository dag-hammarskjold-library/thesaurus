import re
from rdflib import plugin, ConjunctiveGraph, Literal, Namespace, URIRef, RDF
from rdflib.store import Store
from rdflib.namespace import SKOS
from rdflib_sqlalchemy import registerplugins
from flask import Flask
from flask import render_template, abort, request
from config import DevelopmentConfig
from logging import getLogger

registerplugins()

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

logger = getLogger(__name__)

identifier = URIRef(app.config.get('IDENTIFIER', None))
db_uri = Literal(app.config.get('DB_URI'))
per_page = app.config.get("per_page", 20)
store = plugin.get("SQLAlchemy", Store)(identifier=identifier, configuration=db_uri)
graph = ConjunctiveGraph(store)
graph.open(db_uri, create=False)
graph.bind('skos', SKOS)


EU = Namespace('http://eurovoc.europa.eu/schema#')
UNBIST = Namespace('http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#')
ROUTABLES = {
    'Collection': SKOS.Collection,
    'Concept': SKOS.Concept,
    'ConceptScheme': SKOS.ConceptScheme,
    'Domain': EU.Domain,
    'MicroThesaurus': EU.MicroThesaurus,
    'GeographicTerm': UNBIST.GeographicTerm,
}


@app.route('/')
def index():
    lang = request.args.get('lang')
    if request.args.get('aspect'):
        aspect = request.args.get('aspect', None)
    else:
        aspect = 'MicroThesaurus'
    try:
        aspect_uri = ROUTABLES[aspect]
    except KeyError:
        aspect_uri = ROUTABLES['MicroThesaurus']
    page = request.args.get('page')
    if not page:
        page = 1

    results = []
    q = """ SELECT ?subject
            WHERE { ?subject rdf:type <%s> .} order by ?subject
            LIMIT %s OFFSET %s""" % (str(aspect_uri), int(per_page), (int(page) - 1) * int(per_page))
    # for res in graph.subjects(RDF.type, aspect_uri):
    try:
        for res in graph.query(q):
            # r = Resource(graph, res)
            res_label = get_preferred_label(res[0], lang)
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

    return render_template("index.html", context=sorted_results, lang=lang)


@app.route('/term')
def term():
    preferred_language = request.args.get('lang')
    uri_anchor = request.args.get('uri_anchor')
    base_uri = request.args.get('base_uri')
    if not base_uri:
        abort(404)

    uri = base_uri
    if uri_anchor:
        uri = base_uri + '#' + uri_anchor
    pref_label = get_preferred_label(URIRef(uri), preferred_language)
    pref_labels = graph.preferredLabel(URIRef(uri))
    breadcrumbs = []
    breadcrumbs_q = """
        prefix skos: <http://www.w3.org/2004/02/skos/core#>
        prefix unbist: <http://unontologies.s3-website-us-east-1.amazonaws.com/unbist#>
        prefix eu: <http://eurovoc.europa.eu/schema#>
        select ?domain ?microthesaurus where
        {
            {  ?domain skos:member ?microthesaurus . ?microthesaurus skos:member <%s> . }
        union
            { ?domain rdf:type eu:Domain . ?domain skos:member <%s> } .
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
    # for t in [SKOS.relatedMatch, SKOS.broadMatch, SKOS.closeMatch, SKOS.exactMatch, SKOS.narrowMatch]:
    #     matches_q = """
    # select ?" + t.split('#')[1] + " where { <" + uri + "> owl:sameAs ?osa . ?" + t.split('#')[1] +
    # " <" + t + "> ?osa }"""

    #     for m in graph.query(matches_q):
    #         matches.append({'type': t.split('#')[1], 'uri': m})

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
