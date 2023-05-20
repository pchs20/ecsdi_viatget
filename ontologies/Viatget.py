"""
.. module:: ontologies/Viatget

 Translated by owl2rdflib

 Translated to RDFlib from ontology urn:webprotege:ontology:f284b032-799d-4c40-8f60-a429799ce267

 :Date 20/05/2023 12:33:55
"""
from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

PANT =  ClosedNamespace(
    uri=URIRef('https://ontologia.org#'),
    terms=[
        # Classes
        'Activitat',
        'Ciutat',
        'DemanarViatge',
        'ObtenirActivitats',
        'ObtenirTransports',
        'PaquetTancat',
        'PossiblesActivitats',
        'PossiblesTransports',
        'R79kFHXLHEItDb8KIeVk0uU',
        'Allotjament',
        'CompanyiaTransport',
        'ObtenirAllotjaments',
        'Paquet',
        'PossiblesAllotjaments',
        'Resposta',
        'Transport',

        # Object properties
        'informaDelPaquet',
        'teTransportAnada',
        'teTransportTornada',
        'deCiutat',
        'deLaCompanyia',
        'ofereix',
        'teAllotjament',
        'teCiutat',
        'teComAPuntFinal',
        'teComAPuntInici',

        # Data properties
        'activitatsQuantCulturals',
        'activitatsQuantFestives',
        'activitatsQuantLudiques',
        'esCentric',
        'franja',
        'nom',
        'preuMaxim',
        'centric',
        'data',
        'dataFi',
        'dataInici',
        'pressupost',
        'preu',
        'tipus',
        'allotjamentCentric'

        # Named Individuals
    ]
)
