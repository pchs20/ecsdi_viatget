"""
.. module:: ontologies/Viatget

 Translated by owl2rdflib

 Translated to RDFlib from ontology https://ontologia.org#

 :Date 15/05/2023 18:22:56
"""
from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

PANT =  ClosedNamespace(
    uri=URIRef('https://ontologia.org#'),
    terms=[
        # Classes
        'Ciutat',
        'DemanarViatge',
        'PaquetTancat',
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
        'deCiutat',
        'deLaCompanyia',
        'ofereix',
        'teAllotjament',
        'teCiutat',
        'teComAPuntFinal',
        'teComAPuntInici',
        'teTransport',

        # Data properties
        'activitatsQuantCulturals',
        'activitatsQuantFestives',
        'activitatsQuantLudiques',
        'esCentric',
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
