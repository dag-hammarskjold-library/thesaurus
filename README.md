# UNBIS Thesaurus

### General 
Each concept and concept scheme is referenced by a uniform resource identifier (URI) in the form of `https://metadata.un.org/thesaurus#<number>`, where `<number>` conforms to various definitional patterns according to RDF.type.

### Concepts and URIs
The website displays browsable, alphabetical, hyperlinked lists of resources according to the following types:

1. Resources of RDF.type EU.Domain
2. Resources of RDF.type EU.MicroThesaurus
3. Resources of RDF.type SKOS.Concept that are **not** also of RDF.type EU.MicroThesaurus

### Language Settings
By default, the language of the concepts will be set by the browser (if possible) or be set to default of English.  The user can change the language by clicking one of the six language choices on the page (Arabic, Chinese, English, French, Russian or Spanish)

Resources are ordered in the chosen language.  Resources are paginated as needed.

Each resource URI leads to a detailed view landing page for that resource. (default is 25 items per page -- can be configured)

### Detail View
*  Each SKOS.prefLabel that belongs to the resource.
*  Each SKOS.altLabel that belongs to the resource.
*  Each SKOS.scopeNote that belongs to the resource.
*  A breadcrumb consisting of the resource’s parents, from its immediate SKOS.broader to the SKOS.ConceptScheme to which it ultimately belongs.
*  Each relationship characterized as SKOS.broader, SKOS.related, and SKOS.narrower that the resource asserts.
*  Each SKOS.prefLabel for the relationships asserted
*  Each external match characterized as SKOS.exactMatch that is asserted by the resource.  **(TBD)**

### Search
* Elasticsearch is being used as the search back-end.
* The data for each of the resources identified by a URI is be searchable via a search form on the site.
* The search form allows type-ahead lookups of the indexed data.
* Search relevancy for Latin alphabet based languages (English, Fresh and Spanish) has been customized to use edge n-gram tokenization.  Arabic, Chinese and Russian use Elasticsearch's built in language analyzers.
* Search prefers preferred labels but also examines alt labels.
* Search uses the site's current language

### Serialization 
Each node can be serialized into one of four formats (Turtle, XML, JSON-LD, N3).  Clicking on the down arrow right of the node's preferred labels brings up a modal where one can choose the serialization format and whether to download or display on screen.  This functionality can be called from a remote system:
	`POST /api uri=<uri>, format=<format>, dl_location=<on_screen|download>`
Where format is one of 'turtle', 'xml', 'n3' or 'json-ld'
	
### Setup and deployment

install python 3.6

install postgres or have a uri with write privileges

install redis or have a uri ready

install elasticsearch or have a uri ready

`pip install -r requirements.txt`

`python load_all_data.py`

Depending on the environment (local, EC2, AWS Lambda) other steps will be necessary and will be outlined
here.




